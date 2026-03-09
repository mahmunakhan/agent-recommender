"""
Jobs Router
Job posting management, search, AI skill validation, and JD auto-parsing

v2.0 Changes:
- NEW: POST /jobs/validate-skill   → AI agent validates unknown skills (spelling, web verify)
- NEW: POST /jobs/parse-description → AI agent parses JD to auto-fill form fields + extract skills
- Existing endpoints unchanged
"""

import os
import re
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import select, func, or_
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from app.services.database import get_db
from app.services import embedding_service, milvus_service, llm_service
from app.models import Job, JobSkill, Skill, Profile, ProfileSkill, User
from app.schemas import JobCreate, JobResponse, JobDetail
from app.utils import get_current_user
from app.schemas import TokenData

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["Jobs"])

# ============================================================
# Groq LLM helper (reuses project's existing Groq config)
# ============================================================
def _call_groq(system_prompt: str, user_prompt: str, temperature: float = 0.1) -> str:
    """Call Groq API and return text response."""
    try:
        from langchain_groq import ChatGroq
        from langchain_core.messages import SystemMessage, HumanMessage

        llm = ChatGroq(
            model=os.getenv("GROQ_MODEL_PRIMARY", "llama-3.1-8b-instant"),
            temperature=temperature,
            max_tokens=4096,
            api_key=os.getenv("GROQ_API_KEY"),
        )
        resp = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
        return resp.content
    except Exception as e:
        logger.error(f"Groq call failed: {e}")
        raise


# ============================================================
# Pydantic models for the two new endpoints
# ============================================================
class SkillValidateRequest(BaseModel):
    skill_name: str  # e.g. "LangGraph" or "Pythonn"

class SkillValidateResponse(BaseModel):
    is_valid: bool
    corrected_name: str       # Properly-cased / spell-fixed name
    canonical_name: str       # Best official name to use
    category: str             # e.g. "framework", "language", "tool"
    description: str          # One-line description
    confidence: float         # 0.0 – 1.0
    existing_skill_id: Optional[str] = None   # If already in DB
    newly_created_id: Optional[str] = None    # If we just added it

class JDParseRequest(BaseModel):
    description: str  # raw job description text

class JDParseResponse(BaseModel):
    title: Optional[str] = None
    company_name: Optional[str] = None
    location_city: Optional[str] = None
    location_country: Optional[str] = None
    location_type: Optional[str] = None           # onsite / remote / hybrid
    employment_type: Optional[str] = None          # full_time / part_time / contract / internship
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: Optional[str] = None
    experience_min_years: Optional[int] = None
    experience_max_years: Optional[int] = None
    skills: list = []         # [{name, requirement_type, skill_id?}]
    responsibilities: list = []
    benefits: list = []


# ============================================================
# 1) POST /jobs/validate-skill  — AI Skill Validator Agent
# ============================================================
@router.post("/validate-skill", response_model=SkillValidateResponse)
async def validate_skill(
    req: SkillValidateRequest,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Validate a skill name entered by a recruiter.

    Flow:
    1. Check exact / alias match in DB  → return immediately if found.
    2. Check fuzzy match (LIKE) in DB   → return if close match found.
    3. Call Groq AI agent to:
       a. Correct spelling if needed.
       b. Verify the skill is a real technology / competency.
       c. Classify it (language, framework, tool, soft-skill …).
       d. Provide a one-line description.
    4. If valid → insert into `skills` table → return new ID.
    5. If not valid → return is_valid=False.
    """
    raw = req.skill_name.strip()
    if not raw or len(raw) < 2:
        raise HTTPException(status_code=400, detail="Skill name too short")

    # ── Step 1: Exact match (case-insensitive) ──
    existing = db.execute(
        select(Skill).where(func.lower(Skill.name) == raw.lower())
    ).scalar_one_or_none()
    if existing:
        return SkillValidateResponse(
            is_valid=True,
            corrected_name=existing.name,
            canonical_name=existing.name,
            category=existing.skill_type or "technical",
            description=existing.description or "",
            confidence=1.0,
            existing_skill_id=str(existing.id),
        )

    # ── Step 2: Fuzzy DB match (LIKE) ──
    fuzzy = db.execute(
        select(Skill).where(Skill.name.ilike(f"%{raw}%")).limit(5)
    ).scalars().all()
    # Check if any fuzzy result is a very close match (e.g. "React.js" vs "ReactJS")
    for s in fuzzy:
        if _normalize(s.name) == _normalize(raw):
            return SkillValidateResponse(
                is_valid=True,
                corrected_name=s.name,
                canonical_name=s.name,
                category=s.skill_type or "technical",
                description=s.description or "",
                confidence=0.95,
                existing_skill_id=str(s.id),
            )

    # ── Step 3: AI Agent validation via Groq ──
    system_prompt = """You are an expert Technical Skill Validator AI.

Your job: determine whether a user-entered string is a REAL, legitimate technology skill, tool, framework, programming language, methodology, or professional competency.

Rules:
1. If the skill is real → correct any spelling/casing and return details.
2. If it's a misspelling of a known skill → correct it (e.g. "Pythonn" → "Python").
3. If it's a real but newer/niche technology (e.g. "LangGraph", "Crew AI", "Dspy") → accept it.
4. If it's gibberish or not a real skill → reject it.

Respond ONLY with this JSON (no markdown, no backticks):
{
  "is_valid": true/false,
  "corrected_name": "ProperCased Name",
  "canonical_name": "Official Name",
  "category": "one of: language, framework, library, tool, platform, database, methodology, soft_skill, domain, certification, other",
  "description": "One-line description (max 100 chars)",
  "confidence": 0.0-1.0
}"""

    user_prompt = f'Validate this skill: "{raw}"'

    try:
        ai_text = _call_groq(system_prompt, user_prompt, temperature=0.0)
        # Strip markdown fences if present
        ai_text = re.sub(r"```json\s*|```", "", ai_text).strip()
        ai_result = json.loads(ai_text)
    except json.JSONDecodeError:
        logger.warning(f"AI returned non-JSON for skill '{raw}': {ai_text[:200]}")
        # Fallback: treat as valid with low confidence
        ai_result = {
            "is_valid": True,
            "corrected_name": raw,
            "canonical_name": raw,
            "category": "other",
            "description": f"{raw} (unverified skill)",
            "confidence": 0.5,
        }
    except Exception as e:
        logger.error(f"AI skill validation failed: {e}")
        # If AI is down, accept with low confidence rather than blocking recruiter
        ai_result = {
            "is_valid": True,
            "corrected_name": raw,
            "canonical_name": raw,
            "category": "other",
            "description": f"{raw} (AI validation unavailable)",
            "confidence": 0.4,
        }

    is_valid = ai_result.get("is_valid", False)
    corrected = ai_result.get("corrected_name", raw)
    canonical = ai_result.get("canonical_name", corrected)
    category = ai_result.get("category", "other")
    description = ai_result.get("description", "")
    confidence = float(ai_result.get("confidence", 0.5))

    if not is_valid:
        return SkillValidateResponse(
            is_valid=False,
            corrected_name=corrected,
            canonical_name=canonical,
            category=category,
            description=description,
            confidence=confidence,
        )

    # ── Step 4: Re-check DB with corrected name (AI might have fixed spelling) ──
    re_check = db.execute(
        select(Skill).where(func.lower(Skill.name) == canonical.lower())
    ).scalar_one_or_none()
    if re_check:
        return SkillValidateResponse(
            is_valid=True,
            corrected_name=re_check.name,
            canonical_name=re_check.name,
            category=re_check.skill_type or category,
            description=re_check.description or description,
            confidence=max(confidence, 0.9),
            existing_skill_id=str(re_check.id),
        )

    # ── Step 5: Insert new skill into taxonomy ──
    # Map AI category to our skill_type enum
    skill_type_map = {
        "language": "technical",
        "framework": "technical",
        "library": "technical",
        "tool": "tool",
        "platform": "tool",
        "database": "technical",
        "methodology": "domain",
        "soft_skill": "soft",
        "domain": "domain",
        "certification": "certification",
        "other": "technical",
    }
    db_skill_type = skill_type_map.get(category, "technical")

    new_skill = Skill(
        name=canonical,
        slug=canonical.lower().replace(" ", "-").replace(".", "-"),
        skill_type=db_skill_type,
        description=description[:500] if description else None,
        is_verified=False,       # Flagged for admin review later
        popularity_score=0,
        source="recruiter_ai",   # Track how it was added
    )
    try:
        db.add(new_skill)
        db.commit()
        db.refresh(new_skill)
        logger.info(f"New skill added via AI validation: {canonical} (id={new_skill.id})")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to insert new skill '{canonical}': {e}")
        # Skill might already exist due to race condition
        re_check2 = db.execute(
            select(Skill).where(func.lower(Skill.name) == canonical.lower())
        ).scalar_one_or_none()
        if re_check2:
            return SkillValidateResponse(
                is_valid=True,
                corrected_name=re_check2.name,
                canonical_name=re_check2.name,
                category=re_check2.skill_type or category,
                description=re_check2.description or description,
                confidence=confidence,
                existing_skill_id=str(re_check2.id),
            )
        raise HTTPException(status_code=500, detail="Failed to save new skill")

    return SkillValidateResponse(
        is_valid=True,
        corrected_name=canonical,
        canonical_name=canonical,
        category=category,
        description=description,
        confidence=confidence,
        newly_created_id=str(new_skill.id),
    )


# ============================================================
# 2) POST /jobs/parse-description  — JD Auto-Parser Agent
# ============================================================
@router.post("/parse-description", response_model=JDParseResponse)
async def parse_job_description(
    req: JDParseRequest,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Parse a job description and extract structured fields.
    Uses Groq AI to extract: title, location, skills, experience, salary, etc.
    Then matches extracted skills against the DB taxonomy.
    """
    desc = req.description.strip()
    if not desc or len(desc) < 30:
        raise HTTPException(status_code=400, detail="Job description too short (min 30 chars)")

    system_prompt = """You are an expert Job Description Parser AI.

Given a raw job posting description, extract ALL structured fields.

Rules:
1. Extract every field you can find. Use null for fields not mentioned.
2. For skills: list EVERY technology, tool, language, framework, methodology mentioned.
   Mark each as "required", "preferred", or "nice_to_have" based on context.
3. For location_type: infer from text ("remote", "onsite", "hybrid"). Default null.
4. For employment_type: infer ("full_time", "part_time", "contract", "internship"). Default null.
5. For salary: extract numbers and currency if mentioned. Convert to annual if hourly/monthly.
6. Be thorough — extract even skills mentioned casually in responsibilities section.

Respond ONLY with this JSON (no markdown, no backticks, no preamble):
{
  "title": "string or null",
  "company_name": "string or null",
  "location_city": "string or null",
  "location_country": "string or null",
  "location_type": "onsite|remote|hybrid or null",
  "employment_type": "full_time|part_time|contract|internship or null",
  "salary_min": integer_or_null,
  "salary_max": integer_or_null,
  "salary_currency": "USD|SAR|EUR|... or null",
  "experience_min_years": integer_or_null,
  "experience_max_years": integer_or_null,
  "skills": [
    {"name": "Python", "requirement_type": "required"},
    {"name": "LangGraph", "requirement_type": "preferred"}
  ],
  "responsibilities": ["string", "string"],
  "benefits": ["string", "string"]
}"""

    user_prompt = f"Parse this job description:\n\n{desc[:6000]}"

    try:
        ai_text = _call_groq(system_prompt, user_prompt, temperature=0.1)
        ai_text = re.sub(r"```json\s*|```", "", ai_text).strip()
        parsed = json.loads(ai_text)
    except json.JSONDecodeError:
        logger.warning(f"AI JD parse returned non-JSON: {ai_text[:300]}")
        raise HTTPException(status_code=422, detail="AI could not parse the job description. Please try rephrasing.")
    except Exception as e:
        logger.error(f"AI JD parse failed: {e}")
        raise HTTPException(status_code=500, detail="AI parsing service unavailable. Please try again.")

    # ── Match extracted skills against DB taxonomy ──
    extracted_skills = parsed.get("skills", [])
    matched_skills = []

    for sk in extracted_skills:
        name = sk.get("name", "").strip()
        req_type = sk.get("requirement_type", "required")
        if not name:
            continue

        # Try exact match
        db_skill = db.execute(
            select(Skill).where(func.lower(Skill.name) == name.lower())
        ).scalar_one_or_none()

        if db_skill:
            matched_skills.append({
                "name": db_skill.name,
                "requirement_type": req_type,
                "skill_id": str(db_skill.id),
                "in_taxonomy": True,
            })
        else:
            # Try fuzzy match
            fuzzy = db.execute(
                select(Skill).where(Skill.name.ilike(f"%{name}%")).limit(3)
            ).scalars().all()

            best = None
            for f in fuzzy:
                if _normalize(f.name) == _normalize(name):
                    best = f
                    break
            if not best and fuzzy:
                # Pick closest by length similarity
                best = min(fuzzy, key=lambda x: abs(len(x.name) - len(name)))
                # Only accept if reasonably close
                if abs(len(best.name) - len(name)) > 5:
                    best = None

            if best:
                matched_skills.append({
                    "name": best.name,
                    "requirement_type": req_type,
                    "skill_id": str(best.id),
                    "in_taxonomy": True,
                })
            else:
                # Not in taxonomy — frontend will trigger validate-skill for these
                matched_skills.append({
                    "name": name,
                    "requirement_type": req_type,
                    "skill_id": None,
                    "in_taxonomy": False,
                })

    return JDParseResponse(
        title=parsed.get("title"),
        company_name=parsed.get("company_name"),
        location_city=parsed.get("location_city"),
        location_country=parsed.get("location_country"),
        location_type=parsed.get("location_type"),
        employment_type=parsed.get("employment_type"),
        salary_min=_safe_int(parsed.get("salary_min")),
        salary_max=_safe_int(parsed.get("salary_max")),
        salary_currency=parsed.get("salary_currency"),
        experience_min_years=_safe_int(parsed.get("experience_min_years")),
        experience_max_years=_safe_int(parsed.get("experience_max_years")),
        skills=matched_skills,
        responsibilities=parsed.get("responsibilities", []),
        benefits=parsed.get("benefits", []),
    )


# ============================================================
# Helper utilities
# ============================================================
def _normalize(s: str) -> str:
    """Normalize a skill name for comparison: lowercase, strip dots/hyphens/spaces."""
    return re.sub(r"[\s.\-_]+", "", s.lower())


def _safe_int(val) -> Optional[int]:
    """Safely convert to int or return None."""
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


# ============================================================
# EXISTING ENDPOINTS (unchanged)
# ============================================================

@router.get("/")
async def list_jobs(
    search: Optional[str] = None,
    location: Optional[str] = None,
    location_type: Optional[str] = None,
    employment_type: Optional[str] = None,
    salary_min: Optional[int] = None,
    experience_max: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    List and filter jobs.
    """
    query = select(Job).where(Job.is_active == True)
    
    # Text search
    if search:
        query = query.where(
            or_(
                Job.title.ilike(f"%{search}%"),
                Job.company_name.ilike(f"%{search}%"),
                Job.description_raw.ilike(f"%{search}%")
            )
        )
    
    # Location filter
    if location:
        query = query.where(
            or_(
                Job.location_city.ilike(f"%{location}%"),
                Job.location_country.ilike(f"%{location}%")
            )
        )
    
    # Location type filter
    if location_type:
        query = query.where(Job.location_type == location_type)
    
    # Employment type filter
    if employment_type:
        query = query.where(Job.employment_type == employment_type)
    
    # Salary filter
    if salary_min:
        query = query.where(Job.salary_max >= salary_min)
    
    # Experience filter
    if experience_max:
        query = query.where(
            or_(
                Job.experience_min_years <= experience_max,
                Job.experience_min_years == None
            )
        )
    
    # Order by posted date
    query = query.order_by(Job.posted_at.desc(), Job.created_at.desc())
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar()
    
    # Pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    
    jobs = db.execute(query).scalars().all()
    
    return {
        "jobs": [
            {
                "id": j.id,
                "title": j.title,
                "company_name": j.company_name,
                "description_raw": j.description_raw,
                "location_city": j.location_city,
                "location_country": j.location_country,
                "location_type": j.location_type,
                "employment_type": j.employment_type,
                "salary_min": j.salary_min,
                "salary_max": j.salary_max,
                "salary_currency": j.salary_currency,
                "experience_min_years": j.experience_min_years,
                "experience_max_years": j.experience_max_years,
                "is_active": j.is_active,
                "posted_at": j.posted_at,
                "created_at": j.created_at,
                "posted_by_id": j.posted_by_id
            }
            for j in jobs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


@router.post("/", status_code=201)
async def create_job(
    job_data: JobCreate,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new job posting.
    Requires recruiter or admin role.
    """
    if current_user.role not in ["recruiter", "admin"]:
        raise HTTPException(status_code=403, detail="Only recruiters can post jobs")
    
    # Create job with posted_by_id
    new_job = Job(
        title=job_data.title,
        company_name=job_data.company_name,
        description_raw=job_data.description_raw,
        location_city=job_data.location_city,
        location_country=job_data.location_country,
        location_type=job_data.location_type,
        employment_type=job_data.employment_type,
        salary_min=job_data.salary_min,
        salary_max=job_data.salary_max,
        salary_currency=job_data.salary_currency,
        experience_min_years=job_data.experience_min_years,
        experience_max_years=job_data.experience_max_years,
        source_type="internal",
        posted_at=datetime.utcnow(),
        posted_by_id=current_user.user_id,  # Set the recruiter who posted
        is_active=True
    )
    
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    
    # Parse job with LLM to extract requirements
    try:
        parsed = llm_service.parse_job_description(job_data.description_raw)
        if parsed:
            new_job.requirements_json = parsed
            new_job.description_clean = job_data.description_raw[:2000]
            db.commit()
    except Exception as e:
        print(f"LLM parsing error: {e}")
    
    # Generate embedding
    try:
        embedding = embedding_service.generate_job_embedding({
            "title": new_job.title,
            "company_name": new_job.company_name,
            "description_raw": new_job.description_raw
        })
        if embedding:
            milvus_service.insert_job_embedding(new_job.id, embedding)
            new_job.last_vectorized_at = datetime.utcnow()
            db.commit()
    except Exception as e:
        print(f"Embedding error: {e}")
    
    return {
        "id": new_job.id,
        "title": new_job.title,
        "company_name": new_job.company_name,
        "posted_by_id": new_job.posted_by_id,
        "is_active": new_job.is_active,
        "message": "Job created successfully"
    }


@router.put("/{job_id}")
async def update_job(
    job_id: str,
    job_data: dict,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update a job posting.
    Only the recruiter who posted or admin can update.
    """
    job = db.get(Job, job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check permission
    if current_user.role != "admin" and job.posted_by_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this job")
    
    # Update allowed fields
    allowed_fields = [
        "title", "company_name", "description_raw", "location_city",
        "location_country", "location_type", "employment_type",
        "salary_min", "salary_max", "salary_currency",
        "experience_min_years", "experience_max_years", "is_active"
    ]
    
    for field in allowed_fields:
        if field in job_data:
            setattr(job, field, job_data[field])
    
    job.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(job)
    
    # Re-generate embedding if description changed
    if "description_raw" in job_data:
        try:
            embedding = embedding_service.generate_job_embedding({
                "title": job.title,
                "company_name": job.company_name,
                "description_raw": job.description_raw
            })
            if embedding:
                milvus_service.insert_job_embedding(job.id, embedding)
                job.last_vectorized_at = datetime.utcnow()
                db.commit()
        except Exception as e:
            print(f"Embedding update error: {e}")
    
    return {
        "id": job.id,
        "title": job.title,
        "is_active": job.is_active,
        "message": "Job updated successfully"
    }


@router.delete("/{job_id}")
async def delete_job(
    job_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a job posting.
    Only the recruiter who posted or admin can delete.
    """
    job = db.get(Job, job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check permission
    if current_user.role != "admin" and job.posted_by_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this job")
    
    # Delete job skills first
    db.execute(
        JobSkill.__table__.delete().where(JobSkill.job_id == job_id)
    )
    
    # Delete the job
    db.delete(job)
    db.commit()
    
    # Remove from Milvus
    try:
        milvus_service.delete_job_embedding(job_id)
    except Exception as e:
        print(f"Milvus delete error: {e}")
    
    return {"message": "Job deleted successfully"}


@router.get("/{job_id}")
async def get_job(job_id: str, db: Session = Depends(get_db)):
    """
    Get job details.
    """
    job = db.get(Job, job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Get skills
    job_skills = db.execute(
        select(JobSkill, Skill)
        .join(Skill)
        .where(JobSkill.job_id == job_id)
    ).all()
    
    skills = [
        {
            "skill_id": js.JobSkill.skill_id,
            "skill_name": js.Skill.name,
            "requirement_type": js.JobSkill.requirement_type,
            "min_years": js.JobSkill.min_years
        }
        for js in job_skills
    ]
    
    return {
        "id": job.id,
        "title": job.title,
        "company_name": job.company_name,
        "company_logo_url": job.company_logo_url,
        "description_raw": job.description_raw,
        "description_clean": job.description_clean,
        "requirements_json": job.requirements_json,
        "location_city": job.location_city,
        "location_country": job.location_country,
        "location_type": job.location_type,
        "employment_type": job.employment_type,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "salary_currency": job.salary_currency,
        "experience_min_years": job.experience_min_years,
        "experience_max_years": job.experience_max_years,
        "is_active": job.is_active,
        "posted_at": job.posted_at,
        "created_at": job.created_at,
        "posted_by_id": job.posted_by_id,
        "skills": skills
    }


# ============================================================
# 3) GET /jobs/{job_id}/matched-candidates  — AI Candidate Screening
# ============================================================
@router.get("/{job_id}/matched-candidates")
async def get_matched_candidates(
    job_id: str,
    limit: int = Query(50, ge=1, le=100),
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Find candidates whose profiles are most similar to this job.
    
    Uses a composite scoring system:
      - Vector similarity (Milvus cosine): 40% weight  → semantic match
      - Skill overlap:                     35% weight  → hard skill match
      - Experience match:                  25% weight  → years alignment
    
    Returns ranked list of candidates with score breakdowns.
    """
    from app.services.embedding_service import embedding_service as emb_svc
    from app.services.milvus_service import milvus_service as mil_svc

    # ── Permission check ──
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if current_user.role != "admin" and job.posted_by_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to screen candidates for this job")

    # ── Generate job embedding ──
    job_embedding = emb_svc.generate_job_embedding({
        "title": job.title,
        "company_name": job.company_name,
        "description_raw": job.description_raw,
    })
    if not job_embedding:
        raise HTTPException(status_code=500, detail="Failed to generate job embedding")

    # ── Search similar profiles in Milvus ──
    similar_profiles = mil_svc.search_similar_profiles(job_embedding, top_k=limit)
    if not similar_profiles:
        return {"candidates": [], "total": 0, "job_title": job.title}

    # ── Get job's required skills ──
    job_skills_rows = db.execute(
        select(JobSkill, Skill).join(Skill).where(JobSkill.job_id == job_id)
    ).all()
    job_skill_map = {}       # skill_id → {name, requirement_type, min_years}
    job_skill_ids = set()
    for row in job_skills_rows:
        js = row.JobSkill
        sk = row.Skill
        job_skill_ids.add(str(js.skill_id))
        job_skill_map[str(js.skill_id)] = {
            "name": sk.name,
            "requirement_type": js.requirement_type,
            "min_years": js.min_years,
        }

    # ── Build similarity lookup ──
    similarity_map = {p["profile_id"]: p["similarity"] for p in similar_profiles}
    profile_ids = list(similarity_map.keys())

    # ── Fetch profiles ──
    profiles = db.execute(
        select(Profile).where(Profile.id.in_(profile_ids))
    ).scalars().all()

    if not profiles:
        return {"candidates": [], "total": 0, "job_title": job.title}

    # ── Build candidate list with composite scores ──
    candidates = []
    for profile in profiles:
        pid = str(profile.id)
        vector_score = max(0.0, min(1.0, similarity_map.get(pid, 0.0)))

        # Get user info
        user = db.get(User, profile.user_id)
        if not user:
            continue

        # Get profile skills
        p_skills_rows = db.execute(
            select(ProfileSkill, Skill)
            .join(Skill, ProfileSkill.skill_id == Skill.id)
            .where(ProfileSkill.profile_id == profile.id)
        ).all()

        profile_skill_ids = set()
        profile_skill_names = []
        for row in p_skills_rows:
            ps = row.ProfileSkill
            sk = row.Skill
            profile_skill_ids.add(str(ps.skill_id))
            profile_skill_names.append(sk.name)

        # ── Skill match score ──
        matched_skills = []
        missing_skills = []
        if job_skill_ids:
            for sid, info in job_skill_map.items():
                if sid in profile_skill_ids:
                    matched_skills.append(info["name"])
                else:
                    missing_skills.append(info["name"])
            # Weight required skills 2x vs preferred
            required_count = sum(1 for s in job_skill_map.values() if s["requirement_type"] == "required")
            preferred_count = len(job_skill_map) - required_count
            total_weight = (required_count * 2.0) + (preferred_count * 1.0) if job_skill_map else 1.0

            matched_weight = 0.0
            for sid, info in job_skill_map.items():
                if sid in profile_skill_ids:
                    matched_weight += 2.0 if info["requirement_type"] == "required" else 1.0

            skill_score = matched_weight / total_weight if total_weight > 0 else 0.0
        else:
            skill_score = 0.5  # No skills specified — neutral

        # ── Experience match score ──
        candidate_exp = profile.years_experience or 0
        job_min_exp = job.experience_min_years or 0
        job_max_exp = job.experience_max_years or (job_min_exp + 10)

        if job_min_exp == 0 and job_max_exp == 0:
            exp_score = 0.7  # No requirement — slight bonus
        elif job_min_exp <= candidate_exp <= job_max_exp:
            exp_score = 1.0  # Perfect range
        elif candidate_exp > job_max_exp:
            # Overqualified — still decent
            overshoot = candidate_exp - job_max_exp
            exp_score = max(0.3, 1.0 - (overshoot * 0.1))
        elif candidate_exp < job_min_exp:
            # Under-qualified
            shortfall = job_min_exp - candidate_exp
            exp_score = max(0.0, 1.0 - (shortfall * 0.2))
        else:
            exp_score = 0.5

        # ── Composite score ──
        composite = (0.40 * vector_score) + (0.35 * skill_score) + (0.25 * exp_score)

        candidates.append({
            "user_id": str(user.id),
            "profile_id": pid,
            "name": f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email,
            "email": user.email,
            "headline": profile.headline or "",
            "summary": (profile.summary or "")[:200],
            "location_city": profile.location_city or "",
            "location_country": profile.location_country or "",
            "years_experience": candidate_exp,
            "desired_role": profile.desired_role or "",
            "is_open_to_work": profile.is_open_to_work if hasattr(profile, 'is_open_to_work') else True,
            "profile_skills": profile_skill_names[:20],
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "scores": {
                "composite": round(composite * 100, 1),
                "vector_similarity": round(vector_score * 100, 1),
                "skill_match": round(skill_score * 100, 1),
                "experience_match": round(exp_score * 100, 1),
            },
        })

    # Sort by composite score descending
    candidates.sort(key=lambda c: c["scores"]["composite"], reverse=True)

    return {
        "candidates": candidates,
        "total": len(candidates),
        "job_title": job.title,
        "job_skills_count": len(job_skill_ids),
    }


@router.post("/{job_id}/skills")
async def add_job_skill(
    job_id: str,
    skill_data: dict,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add a skill requirement to a job.
    """
    job = db.get(Job, job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check permission
    if current_user.role != "admin" and job.posted_by_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this job")
    
    skill_id = skill_data.get("skill_id")
    requirement_type = skill_data.get("requirement_type", "required")
    min_years = skill_data.get("min_years")
    
    # Check if skill exists
    skill = db.get(Skill, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    
    # Check if already added
    existing = db.execute(
        select(JobSkill).where(
            JobSkill.job_id == job_id,
            JobSkill.skill_id == skill_id
        )
    ).scalar_one_or_none()
    
    if existing:
        # Update existing
        existing.requirement_type = requirement_type
        existing.min_years = min_years
        db.commit()
        return {"message": "Skill updated"}
    
    # Create new
    job_skill = JobSkill(
        job_id=job_id,
        skill_id=skill_id,
        requirement_type=requirement_type,
        min_years=min_years
    )
    db.add(job_skill)
    db.commit()
    
    return {"message": "Skill added to job"}


@router.delete("/{job_id}/skills/{skill_id}")
async def remove_job_skill(
    job_id: str,
    skill_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Remove a skill from a job.
    """
    job = db.get(Job, job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check permission
    if current_user.role != "admin" and job.posted_by_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this job")
    
    job_skill = db.execute(
        select(JobSkill).where(
            JobSkill.job_id == job_id,
            JobSkill.skill_id == skill_id
        )
    ).scalar_one_or_none()
    
    if not job_skill:
        raise HTTPException(status_code=404, detail="Skill not found on this job")
    
    db.delete(job_skill)
    db.commit()
    
    return {"message": "Skill removed from job"}


@router.get("/search/semantic")
async def semantic_search_jobs(
    query: str = Query(..., min_length=3),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Search jobs using semantic similarity.
    """
    # Generate query embedding
    query_embedding = embedding_service.generate_embedding(query)
    
    if not query_embedding:
        raise HTTPException(status_code=500, detail="Failed to generate embedding")
    
    # Search in Milvus
    results = milvus_service.search_similar_jobs(query_embedding, top_k=limit)
    
    if not results:
        return {"jobs": [], "query": query}
    
    # Fetch job details
    job_ids = [r["job_id"] for r in results]
    jobs = db.execute(
        select(Job).where(Job.id.in_(job_ids)).where(Job.is_active == True)
    ).scalars().all()
    
    # Create lookup
    job_lookup = {j.id: j for j in jobs}
    
    # Build response with similarity scores
    response_jobs = []
    for r in results:
        job = job_lookup.get(r["job_id"])
        if job:
            response_jobs.append({
                "id": job.id,
                "title": job.title,
                "company_name": job.company_name,
                "location_city": job.location_city,
                "location_country": job.location_country,
                "location_type": job.location_type,
                "similarity_score": r["similarity"],
                "posted_at": job.posted_at
            })
    
    return {"jobs": response_jobs, "query": query}


@router.get("/recruiter/my-jobs")
async def get_my_jobs(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all jobs posted by the current recruiter.
    """
    if current_user.role not in ["recruiter", "admin"]:
        raise HTTPException(status_code=403, detail="Only recruiters can access this")
    
    jobs = db.execute(
        select(Job)
        .where(Job.posted_by_id == current_user.user_id)
        .order_by(Job.created_at.desc())
    ).scalars().all()
    
    return {
        "jobs": [
            {
                "id": j.id,
                "title": j.title,
                "company_name": j.company_name,
                "description_raw": j.description_raw,
                "location_city": j.location_city,
                "location_country": j.location_country,
                "location_type": j.location_type,
                "employment_type": j.employment_type,
                "salary_min": j.salary_min,
                "salary_max": j.salary_max,
                "salary_currency": j.salary_currency,
                "experience_min_years": j.experience_min_years,
                "is_active": j.is_active,
                "posted_at": j.posted_at,
                "created_at": j.created_at,
                "posted_by_id": j.posted_by_id
            }
            for j in jobs
        ],
        "total": len(jobs)
    }

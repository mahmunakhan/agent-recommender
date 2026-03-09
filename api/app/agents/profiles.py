import os
import re
import io
import json
import logging
import tempfile
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.services.database import get_db
from app.models import User, Profile, ProfileSkill, Skill
from app.schemas import ProfileResponse, ProfileCreate
from app.utils import get_current_user
from app.schemas import TokenData

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profiles", tags=["Profiles"])


class ProfileUpdate(BaseModel):
    headline: Optional[str] = None
    summary: Optional[str] = None
    location_city: Optional[str] = None
    location_country: Optional[str] = None
    years_experience: Optional[int] = None
    desired_role: Optional[str] = None
    desired_salary_min: Optional[int] = None
    desired_salary_max: Optional[int] = None
    is_open_to_work: Optional[bool] = None


# ─── Lazy-load multi-agent processor (heavy imports) ───
_resume_graph = None

def get_resume_graph():
    global _resume_graph
    if _resume_graph is None:
        try:
            from app.agents.skill_taxonomy import SkillTaxonomyManager
            from app.agents.resume_processor import ResumeProcessingGraph
            import os

            base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            taxonomy = SkillTaxonomyManager()
            taxonomy.load_all_sources(
                onet_path=os.path.join(base, "data", "onet", "Technology_Skills.txt"),
                esco_path=os.path.join(base, "data", "esco", "skills_en.csv"),
                custom_path=os.path.join(base, "data", "custom", "custom_skills.json"),
            )
            _resume_graph = ResumeProcessingGraph(taxonomy=taxonomy)
            logger.info("✅ Multi-agent ResumeProcessingGraph initialized")
        except Exception as e:
            logger.error(f"❌ Failed to init ResumeProcessingGraph: {e}")
            _resume_graph = None
    return _resume_graph


# ─── PDF Text Extraction — Column-aware with pdfplumber ───

def extract_pdf_text_pdfplumber(file_bytes: bytes) -> str:
    """Extract text from PDF using pdfplumber with column splitting.
    For 2-column resumes: separates left (experience) from right (skills/certs).
    """
    try:
        import pdfplumber
    except ImportError:
        logger.warning("pdfplumber not installed, returning empty")
        return ""

    sections = []
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for i, page in enumerate(pdf.pages):
                bbox = page.bbox  # (x0, y0, x1, y1)
                x0, y0, x1, y1 = bbox
                w = x1 - x0

                left_text = ""
                right_text = ""
                try:
                    left_crop = page.crop((x0, y0, x0 + w * 0.62, y1))
                    left_text = (left_crop.extract_text(layout=False) or "").strip()

                    right_crop = page.crop((x0 + w * 0.62, y0, x1, y1))
                    right_text = (right_crop.extract_text(layout=False) or "").strip()
                except Exception:
                    left_text = ""
                    right_text = ""

                # If column split produced good results, use it
                if left_text and right_text and len(left_text) > 200:
                    sections.append(f"--- PAGE {i+1} MAIN CONTENT ---\n{left_text}")
                    sections.append(f"--- PAGE {i+1} SIDEBAR ---\n{right_text}")
                else:
                    # Single column page
                    full = (page.extract_text(layout=False) or "").strip()
                    if full:
                        sections.append(f"--- PAGE {i+1} ---\n{full}")

        result = "\n\n".join(sections)
        logger.info(f"pdfplumber extracted: {len(pdf.pages)} pages, {len(result)} chars")
        return result

    except Exception as e:
        logger.error(f"pdfplumber error: {e}")
        return ""


@router.get("/me")
async def get_my_profile(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's profile."""
    profile = db.execute(
        select(Profile).where(Profile.user_id == current_user.user_id)
    ).scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    profile_skills = db.execute(
        select(ProfileSkill, Skill)
        .join(Skill)
        .where(ProfileSkill.profile_id == profile.id)
    ).all()

    skills = [
        {
            "skill_id": ps.ProfileSkill.skill_id,
            "skill_name": ps.Skill.name,
            "proficiency_level": ps.ProfileSkill.proficiency_level,
            "years_experience": ps.ProfileSkill.years_experience,
            "is_primary": ps.ProfileSkill.is_primary
        }
        for ps in profile_skills
    ]

    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "headline": profile.headline,
        "summary": profile.summary,
        "location_city": profile.location_city,
        "location_country": profile.location_country,
        "years_experience": profile.years_experience,
        "desired_role": profile.desired_role,
        "desired_salary_min": profile.desired_salary_min,
        "desired_salary_max": profile.desired_salary_max,
        "is_open_to_work": profile.is_open_to_work,
        "is_verified": profile.is_verified,
        "parsed_json_draft": profile.parsed_json_draft,
        "validated_json": profile.validated_json,
        "skills": skills,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at
    }


@router.put("/me")
async def update_my_profile(
    profile_data: ProfileUpdate,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user's profile."""
    profile = db.execute(
        select(Profile).where(Profile.user_id == current_user.user_id)
    ).scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    update_data = profile_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    profile.updated_at = datetime.utcnow()
    db.commit()

    return {"message": "Profile updated successfully"}


@router.post("/me/resume")
async def upload_resume(
    file: UploadFile = File(...),
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload and parse resume using multi-agent AI system."""
    allowed_types = [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ]

    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF and Word documents allowed.")

    profile = db.execute(
        select(Profile).where(Profile.user_id == current_user.user_id)
    ).scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # ── Read file content ──
    file_content = await file.read()

    # ── Extract text ──
    resume_text = ""
    try:
        if file.content_type == "application/pdf":
            # ★ Try pdfplumber column-aware extraction first (fixes 2-column resumes)
            resume_text = extract_pdf_text_pdfplumber(file_content)

            # Fallback to PyPDF2 if pdfplumber failed
            if not resume_text or len(resume_text.strip()) < 100:
                logger.info("pdfplumber insufficient, falling back to PyPDF2")
                import PyPDF2
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
                resume_text = ""
                for page in pdf_reader.pages:
                    resume_text += page.extract_text() or ""
        else:
            resume_text = file_content.decode("utf-8", errors="ignore")

        profile.resume_text_extracted = resume_text[:50000]
    except Exception as e:
        logger.error(f"Text extraction failed: {e}")
        resume_text = f"Resume file: {file.filename}"
        profile.resume_text_extracted = resume_text

    if len(resume_text.strip()) < 50:
        raise HTTPException(status_code=400, detail="Could not extract enough text from resume. Try a different file.")

    # ── Parse with Multi-Agent System ──
    parsed_data = None
    s3_path = f"local/{current_user.user_id}/{file.filename}"

    try:
        graph = get_resume_graph()

        if graph:
            logger.info(f"🚀 Parsing resume with multi-agent system ({len(resume_text)} chars)")
            parsed_data = graph.process(resume_text, source_file=file.filename or "resume.pdf")
            logger.info(f"✅ Multi-agent parse complete: {parsed_data.get('meta', {}).get('review', {}).get('stats', {})}")
        else:
            logger.warning("⚠️ Multi-agent system unavailable, using basic parser")
            from app.services import llm_service
            parsed_data = llm_service.parse_resume(resume_text)

    except Exception as e:
        logger.error(f"❌ Resume parsing failed: {e}")
        import traceback
        traceback.print_exc()
        parsed_data = None

    # ── Save parsed data to profile ──
    if parsed_data:
        profile.parsed_json_draft = parsed_data
        profile.verification_score = parsed_data.get("meta", {}).get("overall_confidence", 0.7)

        # ★ RESET all profile columns first — prevents old resume data from persisting
        profile.headline = None
        profile.summary = None
        profile.location_city = None
        profile.location_country = None
        profile.years_experience = 0
        profile.desired_role = None
        profile.desired_salary_min = None
        profile.desired_salary_max = None

        pi = parsed_data.get("personal_info", {})

        # Update user name (always overwrite with new resume)
        try:
            user = db.get(User, current_user.user_id)
            if user:
                fn = pi.get("first_name") or ""
                ln = pi.get("last_name") or ""
                if fn:
                    user.first_name = fn
                if ln:
                    user.last_name = ln
        except Exception:
            pass

        # Location
        loc = pi.get("location", {})
        if isinstance(loc, dict):
            profile.location_city = loc.get("city") or None
            profile.location_country = loc.get("country") or None
        elif isinstance(loc, str) and loc:
            if "," in loc:
                parts = loc.split(",")
                profile.location_city = parts[0].strip()
                profile.location_country = parts[-1].strip()
            else:
                profile.location_city = loc

        # Headline
        if pi.get("headline"):
            profile.headline = pi["headline"]
        else:
            exps = parsed_data.get("experience", [])
            if exps and isinstance(exps[0], dict) and exps[0].get("job_title"):
                profile.headline = exps[0]["job_title"]

        # Summary
        if pi.get("summary"):
            profile.summary = pi["summary"]
        else:
            skills_data = parsed_data.get("skills", {})
            all_skills = []
            if isinstance(skills_data, dict):
                for cat in ["skills_technologies", "tools_platforms", "programming_languages", "frameworks", "tools", "technical_skills"]:
                    all_skills.extend(skills_data.get(cat, [])[:3])
            elif isinstance(skills_data, list):
                all_skills = [s.get("name", "") for s in skills_data[:6]]
            if all_skills and profile.headline:
                profile.summary = f"Experienced {profile.headline} with expertise in {', '.join(all_skills[:6])}."

        # Desired role — always derive from current resume
        if pi.get("desired_role"):
            profile.desired_role = pi["desired_role"]
        elif profile.headline:
            profile.desired_role = profile.headline

        # Years of experience — always set (0 for freshers)
        profile.years_experience = _calc_years(parsed_data)

        # ── Add skills to ProfileSkill table ──
        _sync_profile_skills(db, profile, parsed_data)

    profile.resume_s3_path = s3_path
    profile.updated_at = datetime.utcnow()
    db.commit()

    return {
        "message": "Resume uploaded and parsed successfully",
        "s3_path": s3_path,
        "parsed": parsed_data is not None,
        "stats": parsed_data.get("meta", {}).get("review", {}).get("stats") if parsed_data else None,
    }


def _calc_years(parsed_data: dict) -> int:
    """Calculate total years of experience."""
    # Check for explicit years statement
    pi = parsed_data.get("personal_info", {})
    pi_text = str(pi)
    m = re.search(r'(\d+)\+?\s*[Yy]ears?\s*[Ee]xperience', pi_text)
    if m:
        return int(m.group(1))

    # Calculate from date ranges
    all_years = set()
    for exp in parsed_data.get("experience", []):
        start = str(exp.get("start_date") or "").strip()
        end = str(exp.get("end_date") or "present").strip()
        if not start:
            continue
        try:
            start_match = re.search(r'(19|20)\d{2}', start)
            end_match = re.search(r'(19|20)\d{2}', end)
            if start_match:
                all_years.add(int(start_match.group()))
                if end.lower() in ["present", "current", "now", "ongoing", "till date", ""]:
                    all_years.add(datetime.now().year)
                elif end_match:
                    all_years.add(int(end_match.group()))
        except Exception:
            pass

    if len(all_years) >= 2:
        return max(all_years) - min(all_years)
    return 0


def _sync_profile_skills(db: Session, profile: Profile, parsed_data: dict):
    """Sync skills from parsed resume into ProfileSkill table."""
    skills_data = parsed_data.get("skills", {})

    skill_entries = []
    proficiency_map = {}

    if isinstance(skills_data, dict):
        for cat, items in skills_data.items():
            if cat == "skill_proficiency":
                continue
            if isinstance(items, list):
                for name in items:
                    if isinstance(name, str) and name.strip():
                        skill_entries.append({"name": name.strip(), "category": cat})

        for sp in skills_data.get("skill_proficiency", []):
            if isinstance(sp, dict):
                proficiency_map[sp.get("skill", "").lower()] = {
                    "level": sp.get("level", "intermediate"),
                    "years": sp.get("years"),
                }
    elif isinstance(skills_data, list):
        for s in skills_data:
            if isinstance(s, dict) and s.get("name"):
                skill_entries.append({"name": s["name"].strip(), "category": "technical"})
    else:
        return

    added = 0
    for entry in skill_entries:
        skill_name = entry["name"]
        if not skill_name or len(skill_name) < 2:
            continue

        skill = db.execute(
            select(Skill).where(Skill.name.ilike(skill_name))
        ).scalar_one_or_none()

        if not skill:
            skill = db.execute(
                select(Skill).where(Skill.name.ilike(f"%{skill_name}%"))
            ).scalars().first()

        if not skill:
            continue

        existing = db.execute(
            select(ProfileSkill)
            .where(ProfileSkill.profile_id == profile.id)
            .where(ProfileSkill.skill_id == skill.id)
        ).scalar_one_or_none()

        if existing:
            continue

        prof_info = proficiency_map.get(skill_name.lower(), {})
        proficiency = prof_info.get("level", "intermediate")
        years = prof_info.get("years")

        profile_skill = ProfileSkill(
            profile_id=profile.id,
            skill_id=skill.id,
            proficiency_level=proficiency,
            years_experience=float(years) if years else None,
            is_primary=False,
            source="parsed",
        )
        db.add(profile_skill)
        added += 1

    logger.info(f"Added {added} skills to profile from {len(skill_entries)} extracted")


@router.post("/me/verify")
async def verify_profile(
    validated_data: dict,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Verify and finalize parsed profile data."""
    profile = db.execute(
        select(Profile).where(Profile.user_id == current_user.user_id)
    ).scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    profile.validated_json = validated_data
    profile.is_verified = True
    profile.updated_at = datetime.utcnow()

    try:
        from app.services import embedding_service, milvus_service
        embedding = embedding_service.generate_profile_embedding({
            "headline": profile.headline,
            "summary": profile.summary,
            "validated_json": validated_data
        })
        if embedding:
            milvus_service.insert_profile_embedding(profile.id, embedding)
            profile.last_vectorized_at = datetime.utcnow()
    except Exception as e:
        pass

    db.commit()
    return {"message": "Profile verified successfully", "is_verified": True}


class SkillAdd(BaseModel):
    skill_id: str
    proficiency_level: str
    years_experience: Optional[float] = None
    is_primary: bool = False


@router.post("/me/skills")
async def add_skill(
    skill_data: SkillAdd,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a skill to profile."""
    profile = db.execute(
        select(Profile).where(Profile.user_id == current_user.user_id)
    ).scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    skill = db.get(Skill, skill_data.skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    existing = db.execute(
        select(ProfileSkill)
        .where(ProfileSkill.profile_id == profile.id)
        .where(ProfileSkill.skill_id == skill_data.skill_id)
    ).scalar_one_or_none()

    if existing:
        existing.proficiency_level = skill_data.proficiency_level
        existing.years_experience = skill_data.years_experience
        existing.is_primary = skill_data.is_primary
    else:
        profile_skill = ProfileSkill(
            profile_id=profile.id,
            skill_id=skill_data.skill_id,
            proficiency_level=skill_data.proficiency_level,
            years_experience=skill_data.years_experience,
            is_primary=skill_data.is_primary,
            source="manual"
        )
        db.add(profile_skill)

    db.commit()
    return {"message": "Skill added successfully"}


@router.delete("/me/skills/{skill_id}")
async def remove_skill(
    skill_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove a skill from profile."""
    profile = db.execute(
        select(Profile).where(Profile.user_id == current_user.user_id)
    ).scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    profile_skill = db.execute(
        select(ProfileSkill)
        .where(ProfileSkill.profile_id == profile.id)
        .where(ProfileSkill.skill_id == skill_id)
    ).scalar_one_or_none()

    if not profile_skill:
        raise HTTPException(status_code=404, detail="Skill not found in profile")

    db.delete(profile_skill)
    db.commit()
    return {"message": "Skill removed successfully"}


@router.get("/candidate/{user_id}")
async def get_candidate_profile(
    user_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """View a candidate's profile."""
    profile = db.execute(
        select(Profile).where(Profile.user_id == user_id)
    ).scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    candidate = db.execute(
        select(User).where(User.id == user_id)
    ).scalar_one_or_none()

    if not candidate:
        raise HTTPException(status_code=404, detail="User not found")

    if current_user.role == "recruiter" and current_user.user_id != user_id:
        try:
            from app.services.notification_service import NotificationService
            recruiter = db.execute(
                select(User).where(User.id == current_user.user_id)
            ).scalar_one_or_none()
            if recruiter:
                viewer_name = f"{recruiter.first_name} {recruiter.last_name}".strip() or recruiter.email
                NotificationService.notify_profile_view(
                    db=db, candidate_id=user_id, viewer_id=current_user.user_id,
                    viewer_name=viewer_name, company_name="a company"
                )
        except Exception as e:
            logger.warning(f"Profile view notification error: {e}")

    profile_skills = db.execute(
        select(ProfileSkill, Skill)
        .join(Skill)
        .where(ProfileSkill.profile_id == profile.id)
    ).all()

    skills = [
        {
            "skill_id": ps.ProfileSkill.skill_id,
            "skill_name": ps.Skill.name,
            "proficiency_level": ps.ProfileSkill.proficiency_level,
            "years_experience": ps.ProfileSkill.years_experience,
        }
        for ps in profile_skills
    ]

    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "first_name": candidate.first_name,
        "last_name": candidate.last_name,
        "email": candidate.email if current_user.role in ["recruiter", "admin"] else None,
        "headline": profile.headline,
        "summary": profile.summary,
        "location_city": profile.location_city,
        "location_country": profile.location_country,
        "years_experience": profile.years_experience,
        "desired_role": profile.desired_role,
        "is_open_to_work": profile.is_open_to_work,
        "is_verified": profile.is_verified,
        "skills": skills
    }

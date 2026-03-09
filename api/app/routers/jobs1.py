"""
Jobs Router
Job posting management and search
"""

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import select, func, or_
from typing import List, Optional
from datetime import datetime

from app.services.database import get_db
from app.services import embedding_service, milvus_service, llm_service
from app.models import Job, JobSkill, Skill
from app.schemas import JobCreate, JobResponse, JobDetail
from app.utils import get_current_user
from app.schemas import TokenData

router = APIRouter(prefix="/jobs", tags=["Jobs"])


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

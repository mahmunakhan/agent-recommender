"""
Profiles Router
Candidate profile management and resume upload
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
import uuid

from app.services.database import get_db
from app.services import minio_service, embedding_service, milvus_service
from app.models import User, Profile, ProfileSkill, Skill
from app.schemas import ProfileResponse, ProfileCreate
from app.utils import get_current_user
from app.schemas import TokenData

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
    """Upload and parse resume."""
    allowed_types = ["application/pdf", "application/msword",
                     "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]

    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF and Word documents are allowed.")

    profile = db.execute(
        select(Profile).where(Profile.user_id == current_user.user_id)
    ).scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    file_ext = file.filename.split(".")[-1] if file.filename else "pdf"
    object_name = f"{current_user.user_id}/{uuid.uuid4()}.{file_ext}"

    # Read file content
    file_content = await file.read()
    
    # Upload to MinIO
    try:
        import io
        file_io = io.BytesIO(file_content)
        s3_path = minio_service.upload_resume(file_io, object_name, file.content_type)
        profile.resume_s3_path = s3_path
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")

    # Extract text from PDF
    resume_text = ""
    try:
        import io
        if file.content_type == "application/pdf":
            import PyPDF2
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
            for page in pdf_reader.pages:
                resume_text += page.extract_text() or ""
        else:
            # For Word docs, try basic extraction
            resume_text = file_content.decode('utf-8', errors='ignore')
        
        profile.resume_text_extracted = resume_text[:50000]  # Limit size
    except Exception as e:
        resume_text = f"Resume file: {file.filename}"
        profile.resume_text_extracted = resume_text

    # Parse with LLM
    parsed_data = None
    try:
        from app.services import llm_service
        
        if resume_text and len(resume_text) > 50:
            parsed_data = llm_service.parse_resume(resume_text)
            
            if parsed_data:
                profile.parsed_json_draft = parsed_data
                profile.verification_score = 0.7
                
                # Auto-populate profile fields from parsed data
                personal_info = parsed_data.get("personal_info", {})
                if personal_info.get("name"):
                    names = personal_info["name"].split(" ", 1)
                    # Update user first/last name if empty
                    user = db.get(User, current_user.user_id)
                    if user and not user.first_name:
                        user.first_name = names[0] if names else ""
                        user.last_name = names[1] if len(names) > 1 else ""
                
                # Set location from personal info
                if personal_info.get("location"):
                    loc = personal_info["location"]
                    if "," in loc:
                        parts = loc.split(",")
                        profile.location_city = parts[0].strip()
                        profile.location_country = parts[-1].strip()
                    else:
                        profile.location_city = loc
                
                # Set headline from most recent job title
                experience = parsed_data.get("experience", [])
                if experience and len(experience) > 0:
                    latest_job = experience[0]
                    if latest_job.get("title"):
                        profile.headline = latest_job["title"]
                    
                    # Calculate years of experience
                    # Calculate years of experience
                total_years = 0
                for exp in experience:
                    # Try multiple field names
                    start = exp.get("start_date") or exp.get("start") or exp.get("from") or ""
                    end = exp.get("end_date") or exp.get("end") or exp.get("to") or "present"
                    
                    # Convert to string
                    start = str(start).strip()
                    end = str(end).strip()
                    
                    if start:
                        try:
                            # Extract year from various formats: "2018", "2018-01", "Jan 2018", "2018-01-15"
                            import re
                            start_match = re.search(r'(19|20)\d{2}', start)
                            end_match = re.search(r'(19|20)\d{2}', end)
                            
                            if start_match:
                                start_year = int(start_match.group())
                                if end.lower() in ["present", "current", "now", "ongoing", ""]:
                                    end_year = datetime.now().year
                                elif end_match:
                                    end_year = int(end_match.group())
                                else:
                                    end_year = datetime.now().year
                                
                                years = end_year - start_year
                                if years > 0:
                                    total_years += years
                        except Exception as e:
                            print(f"Error parsing dates: {e}")
                            pass
                
                # Also check if experience has 'years' or 'duration' field directly
                if total_years == 0:
                    for exp in experience:
                        years = exp.get("years") or exp.get("duration") or 0
                        if isinstance(years, (int, float)):
                            total_years += int(years)
                
                # Fallback: estimate from skills years
                if total_years == 0 and skills_list:
                    max_skill_years = 0
                    for s in skills_list:
                        skill_years = s.get("years") or s.get("experience") or 0
                        if isinstance(skill_years, (int, float)) and skill_years > max_skill_years:
                            max_skill_years = int(skill_years)
                    if max_skill_years > 0:
                        total_years = max_skill_years
                
                if total_years > 0:
                    profile.years_experience = total_years
                    print(f"Calculated years of experience: {total_years}")
                
                # Build summary from parsed data
                skills_list = parsed_data.get("skills", [])
                skill_names = [s.get("name", "") for s in skills_list[:5]]
                if skill_names and experience:
                    profile.summary = f"Experienced {profile.headline or 'professional'} with expertise in {', '.join(skill_names)}."
                
                # Set desired role same as current headline
                if profile.headline:
                    profile.desired_role = f"Senior {profile.headline}"
                
                # Add skills to profile
                for skill_data in skills_list:
                    skill_name = skill_data.get("name", "").strip()
                    if not skill_name:
                        continue
                    
                    # Find skill in database (case-insensitive)
                    skill = db.execute(
                        select(Skill).where(Skill.name.ilike(f"%{skill_name}%"))
                    ).scalar_one_or_none()
                    
                    if skill:
                        # Check if already added
                        existing = db.execute(
                            select(ProfileSkill)
                            .where(ProfileSkill.profile_id == profile.id)
                            .where(ProfileSkill.skill_id == skill.id)
                        ).scalar_one_or_none()
                        
                        if not existing:
                            proficiency = skill_data.get("proficiency", "intermediate")
                            years = skill_data.get("years", 0)
                            
                            profile_skill = ProfileSkill(
                                profile_id=profile.id,
                                skill_id=skill.id,
                                proficiency_level=proficiency,
                                years_experience=float(years) if years else None,
                                is_primary=False,
                                source="parsed"
                            )
                            db.add(profile_skill)
                
                profile.updated_at = datetime.utcnow()
    except Exception as e:
        import traceback
        traceback.print_exc()

    db.commit()
    return {"message": "Resume uploaded successfully", "s3_path": s3_path, "parsed": parsed_data is not None}


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
    """
    View a candidate's profile.
    For recruiters - tracks profile views and sends notification to candidate.
    """
    # Get the candidate's profile
    profile = db.execute(
        select(Profile).where(Profile.user_id == user_id)
    ).scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Get candidate user info
    candidate = db.execute(
        select(User).where(User.id == user_id)
    ).scalar_one_or_none()
    
    if not candidate:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Track profile view if viewer is a recruiter
    if current_user.role == "recruiter" and current_user.user_id != user_id:
        try:
            from app.services.notification_service import NotificationService
            
            # Get recruiter info
            recruiter = db.execute(
                select(User).where(User.id == current_user.user_id)
            ).scalar_one_or_none()
            
            if recruiter:
                viewer_name = f"{recruiter.first_name} {recruiter.last_name}".strip() or recruiter.email
                # You can add company_name to User model or use a default
                company_name = "a company"  # Can be enhanced later
                
                NotificationService.notify_profile_view(
                    db=db,
                    candidate_id=user_id,
                    viewer_id=current_user.user_id,
                    viewer_name=viewer_name,
                    company_name=company_name
                )
        except Exception as e:
            print(f"Profile view notification error: {e}")
    
    # Get profile skills
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

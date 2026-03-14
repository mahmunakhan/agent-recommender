"""
Talents Router — Recruiter Talent Pool
Browse all candidates, view profiles, invite to apply

Endpoints:
- GET  /recruiter/talents          → Browse all candidates with filters
- GET  /recruiter/talents/{user_id} → View full candidate profile
- POST /recruiter/talents/{user_id}/invite → Invite candidate to apply for a job
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func, or_, desc
from typing import Optional
from datetime import datetime
from pydantic import BaseModel

from app.services.database import get_db
from app.models import User, Profile, ProfileSkill, Skill, Job, Notification
from app.utils import get_current_user
from app.schemas import TokenData

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recruiter/talents", tags=["Recruiter Talents"])


# ── Pydantic models ──
class InviteRequest(BaseModel):
    job_id: str
    message: Optional[str] = None  # Custom invite message


# ============================================================
# 1) GET /recruiter/talents — Browse all candidates
# ============================================================
@router.get("/")
async def browse_talents(
    search: Optional[str] = None,
    skills: Optional[str] = None,       # comma-separated skill names
    location: Optional[str] = None,
    min_experience: Optional[int] = None,
    max_experience: Optional[int] = None,
    is_open_to_work: Optional[bool] = None,
    sort_by: str = Query("recent", regex="^(recent|experience|name)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Browse all candidates on the platform.
    Returns profile summary, skills, location, experience.
    Recruiter can filter by skills, location, experience, open-to-work status.
    """
    if current_user.role not in ["recruiter", "admin"]:
        raise HTTPException(status_code=403, detail="Only recruiters can browse talents")

    # Base query: all candidates with profiles
    query = (
        select(User, Profile)
        .join(Profile, Profile.user_id == User.id)
        .where(User.role == "candidate")
        .where(User.is_active == True)
    )

    # ── Filters ──
    if search:
        query = query.where(
            or_(
                User.first_name.ilike(f"%{search}%"),
                User.last_name.ilike(f"%{search}%"),
                Profile.headline.ilike(f"%{search}%"),
                Profile.summary.ilike(f"%{search}%"),
                Profile.desired_role.ilike(f"%{search}%"),
            )
        )

    if location:
        query = query.where(
            or_(
                Profile.location_city.ilike(f"%{location}%"),
                Profile.location_country.ilike(f"%{location}%"),
            )
        )

    if min_experience is not None:
        query = query.where(Profile.years_experience >= min_experience)

    if max_experience is not None:
        query = query.where(Profile.years_experience <= max_experience)

    if is_open_to_work is not None:
        query = query.where(Profile.is_open_to_work == is_open_to_work)

    # ── Sorting ──
    if sort_by == "recent":
        query = query.order_by(desc(User.created_at))
    elif sort_by == "experience":
        query = query.order_by(desc(Profile.years_experience))
    elif sort_by == "name":
        query = query.order_by(User.first_name, User.last_name)

    # ── Count total ──
    count_q = select(func.count()).select_from(query.subquery())
    total = db.execute(count_q).scalar() or 0

    # ── Pagination ──
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    results = db.execute(query).all()

    # ── Build response with skills ──
    talents = []
    for row in results:
        user = row.User
        profile = row.Profile

        # Get top skills for this profile
        profile_skills = db.execute(
            select(Skill.name, ProfileSkill.proficiency_level)
            .join(ProfileSkill, ProfileSkill.skill_id == Skill.id)
            .where(ProfileSkill.profile_id == profile.id)
            .order_by(desc(ProfileSkill.is_primary))
            .limit(10)
        ).all()

        skill_list = [{"name": s.name, "level": s.proficiency_level} for s in profile_skills]

        # Filter by skills if requested
        if skills:
            requested_skills = [s.strip().lower() for s in skills.split(",")]
            candidate_skill_names = [s["name"].lower() for s in skill_list]
            if not any(rs in " ".join(candidate_skill_names) for rs in requested_skills):
                continue

        talents.append({
            "user_id": str(user.id),
            "profile_id": str(profile.id),
            "name": f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email,
            "email": user.email,
            "headline": profile.headline or "",
            "summary": (profile.summary or "")[:250],
            "location_city": profile.location_city or "",
            "location_country": profile.location_country or "",
            "years_experience": profile.years_experience or 0,
            "desired_role": profile.desired_role or "",
            "is_open_to_work": profile.is_open_to_work if hasattr(profile, "is_open_to_work") else True,
            "is_verified": profile.is_verified or False,
            "skills": skill_list,
            "created_at": str(user.created_at) if user.created_at else None,
        })

    return {
        "talents": talents,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
    }


# ============================================================
# 2) GET /recruiter/talents/{user_id} — View full candidate profile
# ============================================================
@router.get("/{user_id}")
async def get_talent_profile(
    user_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """View a candidate's full profile including parsed resume data."""
    if current_user.role not in ["recruiter", "admin"]:
        raise HTTPException(status_code=403, detail="Only recruiters can view talent profiles")

    user = db.get(User, user_id)
    if not user or user.role != "candidate":
        raise HTTPException(status_code=404, detail="Candidate not found")

    profile = db.execute(
        select(Profile).where(Profile.user_id == user_id)
    ).scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Get all skills
    profile_skills = db.execute(
        select(Skill.name, ProfileSkill.proficiency_level, ProfileSkill.years_experience, ProfileSkill.is_primary)
        .join(ProfileSkill, ProfileSkill.skill_id == Skill.id)
        .where(ProfileSkill.profile_id == profile.id)
    ).all()

    skills = [
        {
            "name": s.name,
            "level": s.proficiency_level,
            "years": s.years_experience,
            "is_primary": s.is_primary,
        }
        for s in profile_skills
    ]

    # Get parsed resume data (experience, education, etc.)
    parsed_data = profile.parsed_json_draft or profile.validated_json or {}

    return {
        "user_id": str(user.id),
        "profile_id": str(profile.id),
        "name": f"{user.first_name or ''} {user.last_name or ''}".strip(),
        "email": user.email,
        "headline": profile.headline or "",
        "summary": profile.summary or "",
        "location_city": profile.location_city or "",
        "location_country": profile.location_country or "",
        "years_experience": profile.years_experience or 0,
        "desired_role": profile.desired_role or "",
        "is_open_to_work": profile.is_open_to_work if hasattr(profile, "is_open_to_work") else True,
        "is_verified": profile.is_verified or False,
        "skills": skills,
        "experience": parsed_data.get("experience", []),
        "education": parsed_data.get("education", []),
        "certifications": parsed_data.get("certifications", []),
        "projects": parsed_data.get("projects", []),
        "languages": parsed_data.get("languages", []),
        "created_at": str(user.created_at) if user.created_at else None,
    }


# ============================================================
# 3) POST /recruiter/talents/{user_id}/invite — Invite to apply
# ============================================================
@router.post("/{user_id}/invite")
async def invite_to_apply(
    user_id: str,
    req: InviteRequest,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Send an invite to a candidate to apply for a specific job.
    Creates a notification for the candidate with the job details.
    """
    if current_user.role not in ["recruiter", "admin"]:
        raise HTTPException(status_code=403, detail="Only recruiters can send invites")

    # Verify candidate exists
    candidate = db.get(User, user_id)
    if not candidate or candidate.role != "candidate":
        raise HTTPException(status_code=404, detail="Candidate not found")

    # Verify job exists and belongs to this recruiter
    job = db.get(Job, req.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if current_user.role != "admin" and job.posted_by_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="You can only invite candidates to your own job postings")

    # Get recruiter info
    recruiter = db.get(User, current_user.user_id)
    recruiter_name = f"{recruiter.first_name or ''} {recruiter.last_name or ''}".strip() if recruiter else "A recruiter"

    # Create notification for the candidate
    custom_msg = req.message or f"Your profile matches our requirements for this role."
    
    notification = Notification(
        user_id=user_id,
        notification_type="job_invite",
        title=f"Invitation to apply: {job.title}",
        message=f"{recruiter_name} from {job.company_name} has invited you to apply for the position of {job.title}. \"{custom_msg}\"",
        action_url=f"/jobs/{job.id}",
        extra_metadata={
            "job_id": str(job.id),
            "job_title": job.title,
            "company_name": job.company_name,
            "recruiter_id": str(current_user.user_id),
            "recruiter_name": recruiter_name,
            "invite_message": custom_msg,
        },
        priority="high",
        channels=["in_app"],
        is_read=False,
        is_sent=True,
        sent_at=datetime.utcnow(),
    )

    db.add(notification)
    db.commit()

    logger.info(f"Recruiter {current_user.user_id} invited candidate {user_id} for job {req.job_id}")

    return {
        "message": f"Invitation sent to {candidate.first_name or candidate.email} for {job.title}",
        "notification_id": str(notification.id),
    }

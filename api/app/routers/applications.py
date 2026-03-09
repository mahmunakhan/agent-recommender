"""
Applications Router — MERGED
Keeps: All existing candidate + recruiter endpoints, NotificationService, ownership checks
Adds: Smart pre-check, match score on apply, AI cover letter, timeline, stats

File: api/app/routers/applications.py
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
import uuid
import logging

from app.services.database import get_db
from app.utils import get_current_user
from app.schemas import TokenData
from app.models import User, Job, Application, Profile, ProfileSkill, Skill, JobSkill, Recommendation

# Import NotificationService safely
try:
    from app.services.notification_service import NotificationService
    HAS_NOTIFICATIONS = True
except ImportError:
    HAS_NOTIFICATIONS = False

# Import RecruiterAction safely (may not exist in all setups)
try:
    from app.models import RecruiterAction
    HAS_RECRUITER_ACTIONS = True
except ImportError:
    HAS_RECRUITER_ACTIONS = False

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/applications", tags=["Applications"])


# ── Schemas ──

class ApplicationCreate(BaseModel):
    job_id: str
    cover_letter: Optional[str] = None
    source: str = "direct"

class ApplicationUpdate(BaseModel):
    status: Optional[str] = None
    recruiter_notes: Optional[str] = None
    rejection_reason: Optional[str] = None


# ══════════════════════════════════════════════════════════════
# HELPER: Calculate skill match between user and job
# ══════════════════════════════════════════════════════════════

def _get_match_data(user_skill_ids: set, job_id: str, db: Session) -> dict:
    """Calculate match score + matched/missing skills."""
    job_skills = db.execute(
        select(JobSkill, Skill).join(Skill).where(JobSkill.job_id == job_id)
    ).all()

    if not job_skills:
        return {"score": 50, "matched": [], "missing": [], "matched_ids": [], "missing_ids": []}

    job_skill_ids = {js.JobSkill.skill_id for js in job_skills}
    required_ids = {js.JobSkill.skill_id for js in job_skills if js.JobSkill.requirement_type == "required"}

    matched_ids = user_skill_ids & job_skill_ids
    missing_ids = required_ids - user_skill_ids

    matched_names = [js.Skill.name for js in job_skills if js.JobSkill.skill_id in matched_ids]
    missing_names = [js.Skill.name for js in job_skills if js.JobSkill.skill_id in missing_ids]

    score = (len(matched_ids) / len(job_skill_ids)) * 100 if job_skill_ids else 50

    return {
        "score": round(score, 1),
        "matched": matched_names,
        "missing": missing_names,
        "matched_ids": list(matched_ids),
        "missing_ids": list(missing_ids),
    }


# ══════════════════════════════════════════════════════════════
# CANDIDATE: POST /applications — Apply to a job
# (EXISTING + ADDED: match score calculation)
# ══════════════════════════════════════════════════════════════

@router.post("")
async def apply_to_job(
    application: ApplicationCreate,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Apply to a job (candidates only). Auto-calculates match score."""
    if current_user.role not in ["candidate", "admin"]:
        raise HTTPException(status_code=403, detail="Only candidates can apply to jobs")

    job = db.execute(select(Job).where(Job.id == application.job_id)).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.is_active:
        raise HTTPException(status_code=400, detail="This job is no longer accepting applications")

    existing = db.execute(
        select(Application).where(
            and_(
                Application.user_id == current_user.user_id,
                Application.job_id == application.job_id
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="You have already applied to this job")

    # Get candidate info
    candidate = db.execute(select(User).where(User.id == current_user.user_id)).scalar_one_or_none()
    candidate_name = f"{candidate.first_name or ''} {candidate.last_name or ''}".strip() or candidate.email

    # ★ NEW: Calculate match score at time of application
    match_score = None
    try:
        profile = db.execute(
            select(Profile).where(Profile.user_id == current_user.user_id)
        ).scalar_one_or_none()

        if profile:
            user_skills = db.execute(
                select(ProfileSkill).where(ProfileSkill.profile_id == profile.id)
            ).scalars().all()
            user_skill_ids = {ps.skill_id for ps in user_skills}
            match = _get_match_data(user_skill_ids, application.job_id, db)
            match_score = match["score"]

            # Use recommendation score if available (more comprehensive)
            rec = db.execute(
                select(Recommendation).where(
                    Recommendation.user_id == current_user.user_id,
                    Recommendation.job_id == application.job_id
                )
            ).scalar_one_or_none()
            if rec:
                match_score = rec.match_score
    except Exception as e:
        logger.warning(f"Could not calculate match score: {e}")

    # Create application
    new_application = Application(
        user_id=current_user.user_id,
        job_id=application.job_id,
        cover_letter=application.cover_letter,
        source=application.source,
        status="applied",
        match_score_at_apply=match_score,
        custom_resume_path=profile.resume_s3_path if profile else None,
    )
    db.add(new_application)
    db.commit()
    db.refresh(new_application)

    # Notify recruiter (EXISTING)
    if job.posted_by_id and HAS_NOTIFICATIONS:
        try:
            NotificationService.notify_new_application(
                db=db,
                recruiter_id=job.posted_by_id,
                candidate_name=candidate_name,
                job_title=job.title,
                application_id=new_application.id
            )
        except Exception as e:
            logger.warning(f"Failed to send notification: {e}")

    return {
        "id": new_application.id,
        "user_id": new_application.user_id,
        "job_id": new_application.job_id,
        "status": new_application.status,
        "cover_letter": new_application.cover_letter,
        "source": new_application.source,
        "match_score_at_apply": round(match_score, 1) if match_score else None,
        "applied_at": new_application.applied_at.isoformat() if new_application.applied_at else None,
        "job_title": job.title,
        "company_name": job.company_name
    }


# ══════════════════════════════════════════════════════════════
# CANDIDATE: GET /applications/my-applications
# (EXISTING + ADDED: stats, timeline)
# ══════════════════════════════════════════════════════════════

@router.get("/my-applications")
async def get_my_applications(
    status: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all applications for current candidate with stats + timeline."""
    query = select(Application, Job).join(Job).where(
        Application.user_id == current_user.user_id
    )
    if status:
        query = query.where(Application.status == status)
    query = query.order_by(Application.applied_at.desc())
    results = db.execute(query).all()

    applications = []
    for app, job in results:
        # ★ NEW: Build status timeline
        timeline = [{"status": "applied", "date": app.applied_at.isoformat() if app.applied_at else None, "note": "Application submitted"}]

        if HAS_RECRUITER_ACTIONS:
            try:
                actions = db.execute(
                    select(RecruiterAction)
                    .where(RecruiterAction.application_id == app.id)
                    .order_by(RecruiterAction.created_at.asc())
                ).scalars().all()
                for action in actions:
                    timeline.append({
                        "status": action.new_status or action.action_type,
                        "date": action.created_at.isoformat() if action.created_at else None,
                        "note": action.notes or f"Status updated to {action.new_status}",
                    })
            except Exception:
                pass

        applications.append({
            "id": app.id,
            "user_id": app.user_id,
            "job_id": app.job_id,
            "status": app.status,
            "cover_letter": app.cover_letter,
            "source": app.source,
            "match_score_at_apply": round(app.match_score_at_apply, 1) if app.match_score_at_apply else None,
            "rejection_reason": app.rejection_reason,
            "applied_at": app.applied_at.isoformat() if app.applied_at else None,
            "status_updated_at": app.status_updated_at.isoformat() if app.status_updated_at else None,
            "job_title": job.title,
            "company_name": job.company_name,
            "location_city": job.location_city,
            "location_country": job.location_country,
            "location_type": getattr(job, 'location_type', None),
            "employment_type": job.employment_type,
            "salary_min": getattr(job, 'salary_min', None),
            "salary_max": getattr(job, 'salary_max', None),
            "salary_currency": getattr(job, 'salary_currency', None),
            "job_is_active": job.is_active,
            "timeline": timeline,
        })

    # ★ NEW: Stats
    status_counts = {}
    for app_data in applications:
        s = app_data["status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    active_set = {'applied', 'screening', 'shortlisted', 'interview_scheduled', 'interviewed', 'offer_extended'}

    return {
        "applications": applications,
        "total": len(applications),
        "stats": {
            "total": len(applications),
            "active": sum(1 for a in applications if a["status"] in active_set),
            "by_status": status_counts,
            "avg_match_score": round(
                sum(a["match_score_at_apply"] or 0 for a in applications) / max(len(applications), 1), 1
            ),
        }
    }


# ══════════════════════════════════════════════════════════════
# CANDIDATE: GET /applications/check/{job_id}
# (REPLACED: now returns FULL pre-check with profile, match, warnings)
# ══════════════════════════════════════════════════════════════

@router.get("/check/{job_id}")
async def check_application_status(
    job_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Smart pre-check before applying.
    Returns: profile snapshot, match score, warnings, already-applied status.
    Used by SmartApplyModal in the frontend.
    """
    # Already applied? Return quick response
    existing = db.execute(
        select(Application).where(
            and_(
                Application.user_id == current_user.user_id,
                Application.job_id == job_id
            )
        )
    ).scalar_one_or_none()

    if existing:
        return {
            "can_apply": False,
            "applied": True,
            "application_id": existing.id,
            "status": existing.status,
            "applied_at": existing.applied_at.isoformat() if existing.applied_at else None,
            "message": f"You already applied on {existing.applied_at.strftime('%b %d, %Y') if existing.applied_at else 'N/A'}"
        }

    # Get profile
    profile = db.execute(
        select(Profile).where(Profile.user_id == current_user.user_id)
    ).scalar_one_or_none()

    if not profile:
        return {
            "can_apply": False,
            "applied": False,
            "message": "Profile not found. Create your profile first.",
            "warnings": [{"type": "profile", "severity": "high", "message": "No profile found. Create one first."}]
        }

    user = db.get(User, current_user.user_id)
    job = db.get(Job, job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Get user skills
    user_skills = db.execute(
        select(ProfileSkill, Skill).join(Skill).where(ProfileSkill.profile_id == profile.id)
    ).all()
    user_skill_ids = {ps.ProfileSkill.skill_id for ps in user_skills}
    user_skill_names = [ps.Skill.name for ps in user_skills]

    # Match score
    match = _get_match_data(user_skill_ids, job_id, db)

    # Recommendation score if exists
    rec = db.execute(
        select(Recommendation).where(
            Recommendation.user_id == current_user.user_id,
            Recommendation.job_id == job_id
        )
    ).scalar_one_or_none()

    # Build warnings
    warnings = []
    if not profile.is_verified:
        warnings.append({"type": "profile", "severity": "high", "message": "Profile not verified. Verify for better chances."})
    if not profile.resume_s3_path:
        warnings.append({"type": "resume", "severity": "high", "message": "No resume uploaded. Upload to strengthen your application."})
    if len(user_skill_names) < 5:
        warnings.append({"type": "skills", "severity": "medium", "message": f"Only {len(user_skill_names)} skills on profile. Add more."})
    if match["score"] < 30:
        warnings.append({"type": "match", "severity": "high", "message": f"Low skill match ({match['score']}%). Missing {len(match['missing'])} required skills."})
    elif match["score"] < 50:
        warnings.append({"type": "match", "severity": "medium", "message": f"Moderate match ({match['score']}%). Consider learning: {', '.join(match['missing'][:3])}"})
    if job.experience_min_years and profile.years_experience:
        if profile.years_experience < job.experience_min_years:
            warnings.append({"type": "experience", "severity": "medium", "message": f"Job needs {job.experience_min_years}+ years. You have {profile.years_experience}."})

    return {
        "can_apply": True,
        "applied": False,
        "job": {
            "id": str(job.id),
            "title": job.title,
            "company_name": job.company_name,
            "location_city": job.location_city,
            "location_type": getattr(job, 'location_type', None),
            "experience_min_years": job.experience_min_years,
            "salary_min": getattr(job, 'salary_min', None),
            "salary_max": getattr(job, 'salary_max', None),
            "salary_currency": getattr(job, 'salary_currency', None),
        },
        "profile": {
            "name": f"{user.first_name or ''} {user.last_name or ''}".strip(),
            "email": user.email,
            "headline": profile.headline,
            "summary": profile.summary,
            "location": f"{profile.location_city or ''}, {profile.location_country or ''}".strip(", "),
            "years_experience": profile.years_experience,
            "desired_role": profile.desired_role,
            "skills": user_skill_names,
            "has_resume": bool(profile.resume_s3_path),
            "is_verified": profile.is_verified,
        },
        "match": {
            "score": match["score"],
            "overall_score": round(rec.match_score, 1) if rec else None,
            "matched_skills": match["matched"],
            "missing_skills": match["missing"],
        },
        "warnings": warnings,
    }


# ══════════════════════════════════════════════════════════════
# CANDIDATE: DELETE /applications/{application_id} — Withdraw
# (EXISTING, kept as-is)
# ══════════════════════════════════════════════════════════════

@router.delete("/{application_id}")
async def withdraw_application(
    application_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Withdraw an application (candidates only)"""
    application = db.execute(
        select(Application).where(Application.id == application_id)
    ).scalar_one_or_none()

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    if application.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="You can only withdraw your own applications")
    if application.status not in ["applied", "screening"]:
        raise HTTPException(status_code=400, detail="Cannot withdraw application at this stage")

    application.status = "withdrawn"
    application.status_updated_at = datetime.utcnow()

    # Log action if RecruiterAction model exists
    if HAS_RECRUITER_ACTIONS:
        try:
            action = RecruiterAction(
                id=str(uuid.uuid4()),
                application_id=application.id,
                recruiter_id=current_user.user_id,
                action_type="status_changed",
                previous_status="applied",
                new_status="withdrawn",
                notes="Candidate withdrew application",
            )
            db.add(action)
        except Exception:
            pass

    db.commit()
    return {"message": "Application withdrawn successfully"}


# ══════════════════════════════════════════════════════════════
# ★ NEW: AI COVER LETTER — POST /applications/generate-cover-letter
# ══════════════════════════════════════════════════════════════

@router.post("/generate-cover-letter")
async def generate_cover_letter(
    job_id: str = Query(...),
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """AI-generate cover letter from profile + job data. Zero input needed."""
    profile = db.execute(
        select(Profile).where(Profile.user_id == current_user.user_id)
    ).scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    user = db.get(User, current_user.user_id)
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Get skills + match
    user_skills = db.execute(
        select(ProfileSkill, Skill).join(Skill).where(ProfileSkill.profile_id == profile.id)
    ).all()
    skill_names = [ps.Skill.name for ps in user_skills]
    user_skill_ids = {ps.ProfileSkill.skill_id for ps in user_skills}
    match = _get_match_data(user_skill_ids, job_id, db)

    name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Candidate"

    try:
        from app.services.llm_service import llm_service

        prompt = f"""Write a professional cover letter for this job application.

CANDIDATE:
- Name: {name}
- Current Role: {profile.headline or 'N/A'}
- Experience: {profile.years_experience or 'N/A'} years
- Key Skills: {', '.join(skill_names[:15])}
- Summary: {(profile.summary or 'N/A')[:300]}

JOB:
- Title: {job.title}
- Company: {job.company_name or 'the company'}
- Location: {job.location_city or ''} ({getattr(job, 'location_type', '') or ''})

SKILL MATCH:
- Matching Skills: {', '.join(match['matched'][:8])}
- Skills to Address: {', '.join(match['missing'][:3]) or 'None'}

Write 3-4 paragraphs:
1. Opening — excitement about this specific role
2. Relevant experience and matching skills
3. How you'd add value; address any gaps positively
4. Closing with call to action

Use the actual names provided. Professional but personable tone.
Return ONLY the cover letter text, nothing else."""

        response = llm_service._call_llm(prompt, temperature=0.3, max_tokens=1500)

        if response:
            return {"cover_letter": response, "job_title": job.title, "company": job.company_name}
        else:
            raise HTTPException(status_code=500, detail="AI generation failed")
    except Exception as e:
        logger.error(f"Cover letter generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cover letter generation failed: {str(e)}")


# ══════════════════════════════════════════════════════════════
# RECRUITER: GET /applications/job/{job_id}
# (EXISTING, kept as-is)
# ══════════════════════════════════════════════════════════════

@router.get("/job/{job_id}")
async def get_job_applications(
    job_id: str,
    status: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all applications for a specific job (recruiters only)"""
    if current_user.role not in ["recruiter", "admin"]:
        raise HTTPException(status_code=403, detail="Only recruiters can view applications")

    job = db.execute(select(Job).where(Job.id == job_id)).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if current_user.role != "admin" and job.posted_by_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to view applications for this job")

    query = select(Application, User, Profile).join(
        User, Application.user_id == User.id
    ).outerjoin(
        Profile, User.id == Profile.user_id
    ).where(Application.job_id == job_id)

    if status:
        query = query.where(Application.status == status)

    query = query.order_by(Application.applied_at.desc())
    results = db.execute(query).all()

    applications = []
    for app, user, profile_obj in results:
        applications.append({
            "id": app.id,
            "user_id": app.user_id,
            "job_id": app.job_id,
            "status": app.status,
            "cover_letter": app.cover_letter,
            "source": app.source,
            "match_score_at_apply": round(app.match_score_at_apply, 1) if app.match_score_at_apply else None,
            "recruiter_notes": app.recruiter_notes,
            "rejection_reason": app.rejection_reason,
            "applied_at": app.applied_at.isoformat() if app.applied_at else None,
            "status_updated_at": app.status_updated_at.isoformat() if app.status_updated_at else None,
            "applicant_name": f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email,
            "applicant_email": user.email,
            "headline": profile_obj.headline if profile_obj else None,
            "years_experience": profile_obj.years_experience if profile_obj else None
        })

    counts = db.execute(
        select(Application.status, func.count(Application.id))
        .where(Application.job_id == job_id)
        .group_by(Application.status)
    ).all()
    status_counts = {s: c for s, c in counts}

    return {"applications": applications, "total": len(applications), "status_counts": status_counts}


# ══════════════════════════════════════════════════════════════
# RECRUITER: PUT /applications/{application_id}
# (EXISTING, kept as-is with notifications)
# ══════════════════════════════════════════════════════════════

@router.put("/{application_id}")
async def update_application(
    application_id: str,
    update_data: ApplicationUpdate,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update application status (recruiters only)"""
    if current_user.role not in ["recruiter", "admin"]:
        raise HTTPException(status_code=403, detail="Only recruiters can update applications")

    application = db.execute(
        select(Application).where(Application.id == application_id)
    ).scalar_one_or_none()

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    job = db.execute(select(Job).where(Job.id == application.job_id)).scalar_one_or_none()
    if current_user.role != "admin" and job and job.posted_by_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this application")

    old_status = application.status

    if update_data.status:
        valid_statuses = ["applied", "screening", "shortlisted", "interview_scheduled",
                          "interviewed", "offer_extended", "offer_accepted", "offer_declined", "rejected"]
        if update_data.status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
        application.status = update_data.status
        application.status_updated_at = datetime.utcnow()

    if update_data.recruiter_notes is not None:
        application.recruiter_notes = update_data.recruiter_notes
    if update_data.rejection_reason is not None:
        application.rejection_reason = update_data.rejection_reason

    # Log action
    if HAS_RECRUITER_ACTIONS:
        try:
            action = RecruiterAction(
                id=str(uuid.uuid4()),
                application_id=application.id,
                recruiter_id=current_user.user_id,
                action_type="status_changed" if update_data.status else "note_added",
                previous_status=old_status,
                new_status=update_data.status or old_status,
                notes=update_data.recruiter_notes or f"Status changed to {update_data.status}",
            )
            db.add(action)
        except Exception:
            pass

    db.commit()
    db.refresh(application)

    # Notify candidate (EXISTING)
    if update_data.status and update_data.status != old_status and HAS_NOTIFICATIONS and job:
        try:
            NotificationService.notify_status_update(
                db=db,
                candidate_id=application.user_id,
                job_title=job.title,
                company_name=job.company_name,
                new_status=update_data.status,
                application_id=application.id
            )
        except Exception as e:
            logger.warning(f"Failed to send notification: {e}")

    return {
        "id": application.id,
        "status": application.status,
        "recruiter_notes": application.recruiter_notes,
        "rejection_reason": application.rejection_reason,
        "status_updated_at": application.status_updated_at.isoformat() if application.status_updated_at else None,
        "message": "Application updated successfully"
    }


# ══════════════════════════════════════════════════════════════
# RECRUITER: GET /applications/recruiter/all
# (EXISTING, kept as-is)
# ══════════════════════════════════════════════════════════════

@router.get("/recruiter/all")
async def get_all_recruiter_applications(
    status: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all applications across all jobs for the current recruiter"""
    if current_user.role not in ["recruiter", "admin"]:
        raise HTTPException(status_code=403, detail="Only recruiters can access this")

    if current_user.role == "admin":
        jobs_subquery = select(Job.id)
    else:
        jobs_subquery = select(Job.id).where(Job.posted_by_id == current_user.user_id)

    query = select(Application, Job, User).join(
        Job, Application.job_id == Job.id
    ).join(
        User, Application.user_id == User.id
    ).where(Application.job_id.in_(jobs_subquery))

    if status:
        query = query.where(Application.status == status)

    query = query.order_by(Application.applied_at.desc())
    results = db.execute(query).all()

    applications = []
    for app, job, user in results:
        applications.append({
            "id": app.id,
            "user_id": app.user_id,
            "job_id": app.job_id,
            "status": app.status,
            "cover_letter": app.cover_letter,
            "match_score_at_apply": round(app.match_score_at_apply, 1) if app.match_score_at_apply else None,
            "applied_at": app.applied_at.isoformat() if app.applied_at else None,
            "job_title": job.title,
            "company_name": job.company_name,
            "applicant_name": f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email,
            "applicant_email": user.email
        })

    return {"applications": applications, "total": len(applications)}

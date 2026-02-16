"""
Applications Router
Handles job application endpoints for candidates and recruiters
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
from app.services.database import get_db
from app.utils import get_current_user
from app.schemas import TokenData
from app.models import User, Job, Application, Profile
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/applications", tags=["Applications"])

# Pydantic schemas
class ApplicationCreate(BaseModel):
    job_id: str
    cover_letter: Optional[str] = None
    source: str = "direct"

class ApplicationUpdate(BaseModel):
    status: Optional[str] = None
    recruiter_notes: Optional[str] = None
    rejection_reason: Optional[str] = None


# ============ CANDIDATE ENDPOINTS ============

@router.post("")
async def apply_to_job(
    application: ApplicationCreate,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Apply to a job (candidates only)"""
    if current_user.role not in ["candidate", "admin"]:
        raise HTTPException(status_code=403, detail="Only candidates can apply to jobs")

    # Check if job exists and is active
    job = db.execute(select(Job).where(Job.id == application.job_id)).scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job.is_active:
        raise HTTPException(status_code=400, detail="This job is no longer accepting applications")

    # Check if already applied
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

    # Get candidate info for notification
    candidate = db.execute(select(User).where(User.id == current_user.user_id)).scalar_one_or_none()
    candidate_name = f"{candidate.first_name or ''} {candidate.last_name or ''}".strip() or candidate.email

    # Create application
    new_application = Application(
        user_id=current_user.user_id,
        job_id=application.job_id,
        cover_letter=application.cover_letter,
        source=application.source,
        status="applied"
    )

    db.add(new_application)
    db.commit()
    db.refresh(new_application)

    # Notify recruiter about new application
    if job.posted_by_id:
        try:
            NotificationService.notify_new_application(
                db=db,
                recruiter_id=job.posted_by_id,
                candidate_name=candidate_name,
                job_title=job.title,
                application_id=new_application.id
            )
        except Exception as e:
            print(f"Failed to send notification: {e}")

    return {
        "id": new_application.id,
        "user_id": new_application.user_id,
        "job_id": new_application.job_id,
        "status": new_application.status,
        "cover_letter": new_application.cover_letter,
        "source": new_application.source,
        "applied_at": new_application.applied_at.isoformat() if new_application.applied_at else None,
        "job_title": job.title,
        "company_name": job.company_name
    }


@router.get("/my-applications")
async def get_my_applications(
    status: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all applications for current candidate"""
    query = select(Application, Job).join(Job).where(
        Application.user_id == current_user.user_id
    )

    if status:
        query = query.where(Application.status == status)

    query = query.order_by(Application.applied_at.desc())
    results = db.execute(query).all()

    applications = []
    for app, job in results:
        applications.append({
            "id": app.id,
            "user_id": app.user_id,
            "job_id": app.job_id,
            "status": app.status,
            "cover_letter": app.cover_letter,
            "source": app.source,
            "match_score_at_apply": app.match_score_at_apply,
            "rejection_reason": app.rejection_reason,
            "applied_at": app.applied_at.isoformat() if app.applied_at else None,
            "status_updated_at": app.status_updated_at.isoformat() if app.status_updated_at else None,
            "job_title": job.title,
            "company_name": job.company_name,
            "location_city": job.location_city,
            "location_country": job.location_country,
            "employment_type": job.employment_type
        })

    return {"applications": applications, "total": len(applications)}


@router.get("/check/{job_id}")
async def check_application_status(
    job_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Check if current user has applied to a specific job"""
    application = db.execute(
        select(Application).where(
            and_(
                Application.user_id == current_user.user_id,
                Application.job_id == job_id
            )
        )
    ).scalar_one_or_none()

    if application:
        return {
            "applied": True,
            "application_id": application.id,
            "status": application.status,
            "applied_at": application.applied_at.isoformat() if application.applied_at else None
        }
    return {"applied": False}


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
    db.commit()

    return {"message": "Application withdrawn successfully"}


# ============ RECRUITER ENDPOINTS ============

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

    # Check job ownership
    job = db.execute(select(Job).where(Job.id == job_id)).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if current_user.role != "admin" and job.posted_by_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to view applications for this job")

    # Get applications with user info
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
    for app, user, profile in results:
        applications.append({
            "id": app.id,
            "user_id": app.user_id,
            "job_id": app.job_id,
            "status": app.status,
            "cover_letter": app.cover_letter,
            "source": app.source,
            "match_score_at_apply": app.match_score_at_apply,
            "recruiter_notes": app.recruiter_notes,
            "rejection_reason": app.rejection_reason,
            "applied_at": app.applied_at.isoformat() if app.applied_at else None,
            "status_updated_at": app.status_updated_at.isoformat() if app.status_updated_at else None,
            "applicant_name": f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email,
            "applicant_email": user.email,
            "headline": profile.headline if profile else None,
            "years_experience": profile.years_experience if profile else None
        })

    # Get status counts
    counts = db.execute(
        select(Application.status, func.count(Application.id))
        .where(Application.job_id == job_id)
        .group_by(Application.status)
    ).all()
    status_counts = {s: c for s, c in counts}

    return {
        "applications": applications,
        "total": len(applications),
        "status_counts": status_counts
    }


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

    # Check job ownership
    job = db.execute(select(Job).where(Job.id == application.job_id)).scalar_one_or_none()
    if current_user.role != "admin" and job.posted_by_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this application")

    old_status = application.status

    # Update fields
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

    db.commit()
    db.refresh(application)

    # Notify candidate about status change
    if update_data.status and update_data.status != old_status:
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
            print(f"Failed to send notification: {e}")

    return {
        "id": application.id,
        "status": application.status,
        "recruiter_notes": application.recruiter_notes,
        "rejection_reason": application.rejection_reason,
        "status_updated_at": application.status_updated_at.isoformat() if application.status_updated_at else None,
        "message": "Application updated successfully"
    }


@router.get("/recruiter/all")
async def get_all_recruiter_applications(
    status: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all applications across all jobs for the current recruiter"""
    if current_user.role not in ["recruiter", "admin"]:
        raise HTTPException(status_code=403, detail="Only recruiters can access this")

    # Get jobs posted by this recruiter
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
            "applied_at": app.applied_at.isoformat() if app.applied_at else None,
            "job_title": job.title,
            "company_name": job.company_name,
            "applicant_name": f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email,
            "applicant_email": user.email
        })

    return {"applications": applications, "total": len(applications)}

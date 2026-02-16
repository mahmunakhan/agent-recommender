from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.services.database import get_db
from app.utils import get_current_user
from app.schemas import TokenData
from app.services.background_service import BackgroundJobService

router = APIRouter(prefix="/admin/tasks", tags=["Admin Tasks"])


@router.post("/check-expiring-jobs")
async def check_expiring_jobs(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Manually trigger check for expiring jobs.
    Admin only.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    notified_count = BackgroundJobService.check_expiring_jobs(db)
    
    return {
        "message": f"Checked for expiring jobs",
        "notifications_sent": notified_count
    }


@router.post("/send-job-matches/{job_id}")
async def send_job_match_notifications(
    job_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Manually trigger job match notifications for a specific job.
    Admin only.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    notified_count = BackgroundJobService.send_job_match_notifications(db, job_id)
    
    return {
        "message": f"Job match notifications sent",
        "job_id": job_id,
        "notifications_sent": notified_count
    }

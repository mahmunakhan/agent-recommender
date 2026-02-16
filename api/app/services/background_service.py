from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime, timedelta
from typing import List
from app.models.job import Job
from app.models.user import User
from app.services.notification_service import NotificationService
import logging

logger = logging.getLogger(__name__)


class BackgroundJobService:
    """Service to run scheduled notification tasks."""
    
    @staticmethod
    def check_expiring_jobs(db: Session, days_before: List[int] = [7, 3, 1]):
        """
        Check for jobs expiring soon and send notifications.
        Runs daily to notify recruiters about expiring job postings.
        
        Args:
            db: Database session
            days_before: List of days before expiration to notify (default: 7, 3, 1 days)
        """
        notified_count = 0
        
        for days in days_before:
            target_date = datetime.utcnow().date() + timedelta(days=days)
            
            # Find jobs expiring on this target date
            expiring_jobs = db.query(Job).filter(
                and_(
                    Job.is_active == True,
                    Job.expires_at != None,
                    Job.expires_at >= datetime.combine(target_date, datetime.min.time()),
                    Job.expires_at < datetime.combine(target_date + timedelta(days=1), datetime.min.time())
                )
            ).all()
            
            for job in expiring_jobs:
                try:
                    # Check if we already sent a notification for this job and days_remaining
                    from app.models.system import Notification
                    existing = db.query(Notification).filter(
                        and_(
                            Notification.user_id == job.posted_by_id,
                            Notification.notification_type == 'job_expiring',
                            Notification.extra_metadata.contains({'job_id': str(job.id), 'days_remaining': days})
                        )
                    ).first()
                    
                    if not existing:
                        NotificationService.notify_job_expiring(
                            db=db,
                            recruiter_id=job.posted_by_id,
                            job_id=str(job.id),
                            job_title=job.title,
                            company_name=job.company_name,
                            days_remaining=days
                        )
                        notified_count += 1
                        logger.info(f"Sent expiring notification for job {job.id} ({days} days remaining)")
                except Exception as e:
                    logger.error(f"Failed to send expiring notification for job {job.id}: {str(e)}")
        
        return notified_count

    @staticmethod
    def send_job_match_notifications(db: Session, job_id: str):
        """
        Send notifications to candidates who match a newly posted job.
        Called when a new job is created.
        
        Args:
            db: Database session
            job_id: ID of the newly created job
        """
        from app.models.candidate import CandidateProfile
        
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return 0
        
        # Get all active candidates
        candidates = db.query(CandidateProfile).filter(
            CandidateProfile.is_open_to_work == True
        ).all()
        
        notified_count = 0
        
        for candidate in candidates:
            try:
                # Simple match score calculation (can be enhanced with ML)
                match_score = BackgroundJobService._calculate_simple_match(candidate, job)
                
                # Only notify for matches above 60%
                if match_score >= 60:
                    NotificationService.notify_job_match(
                        db=db,
                        candidate_id=candidate.user_id,
                        job_id=str(job.id),
                        job_title=job.title,
                        company_name=job.company_name,
                        match_score=match_score
                    )
                    notified_count += 1
            except Exception as e:
                logger.error(f"Failed to send match notification to candidate {candidate.user_id}: {str(e)}")
        
        return notified_count

    @staticmethod
    def _calculate_simple_match(candidate, job) -> int:
        """Calculate a simple match score between candidate and job."""
        score = 50  # Base score
        
        # Location match
        if candidate.location_city and job.location_city:
            if candidate.location_city.lower() == job.location_city.lower():
                score += 15
        
        # Experience match
        if candidate.years_experience and job.experience_min_years:
            if candidate.years_experience >= job.experience_min_years:
                score += 20
            elif candidate.years_experience >= job.experience_min_years - 1:
                score += 10
        
        # Desired role match (simple keyword check)
        if candidate.desired_role and job.title:
            if any(word.lower() in job.title.lower() for word in candidate.desired_role.split()):
                score += 15
        
        return min(score, 100)

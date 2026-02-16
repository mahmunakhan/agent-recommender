from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional, List
from datetime import datetime
from app.models.system import Notification
from app.models.user import User
from app.services.email_service import send_application_received_email, send_status_update_email
import logging

logger = logging.getLogger(__name__)


class NotificationService:
    @staticmethod
    def create_notification(
        db: Session,
        user_id: str,
        notification_type: str,
        title: str,
        message: str,
        action_url: Optional[str] = None,
        priority: str = 'normal',
        metadata: Optional[dict] = None,
        send_email: bool = False
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            message=message,
            action_url=action_url,
            priority=priority,
            extra_metadata=metadata,
            channels=['in_app', 'email'] if send_email else ['in_app']
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)
        return notification

    @staticmethod
    def get_user_notifications(
        db: Session,
        user_id: str,
        unread_only: bool = False,
        limit: int = 50
    ) -> List[Notification]:
        query = db.query(Notification).filter(Notification.user_id == user_id)
        if unread_only:
            query = query.filter(Notification.is_read == False)
        return query.order_by(desc(Notification.created_at)).limit(limit).all()

    @staticmethod
    def get_unread_count(db: Session, user_id: str) -> int:
        return db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read == False
        ).count()
    
    @staticmethod
    def mark_as_read(db: Session, notification_id: str, user_id: str) -> bool:
        notification = db.query(Notification).filter(
            Notification.id == notification_id,
            Notification.user_id == user_id
        ).first()
        if notification:
            notification.is_read = True
            notification.read_at = datetime.utcnow()
            db.commit()
            return True
        return False
    
    @staticmethod
    def mark_all_as_read(db: Session, user_id: str) -> int:
        count = db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read == False
        ).update({'is_read': True, 'read_at': datetime.utcnow()})
        db.commit()
        return count

    # Application-specific notifications with email
    @staticmethod
    def notify_new_application(
        db: Session,
        recruiter_id: str,
        candidate_name: str,
        job_title: str,
        application_id: str
    ):
        # Get recruiter email
        recruiter = db.query(User).filter(User.id == recruiter_id).first()
        
        # Create in-app notification
        notification = NotificationService.create_notification(
            db=db,
            user_id=recruiter_id,
            notification_type='application_received',
            title='New Job Application',
            message=f'{candidate_name} applied for {job_title}',
            action_url=f'/recruiter/applications/{application_id}',
            priority='normal',
            metadata={'application_id': application_id, 'candidate_name': candidate_name},
            send_email=True
        )
        
        # Send email notification
        if recruiter and recruiter.email:
            try:
                send_application_received_email(
                    recruiter_email=recruiter.email,
                    candidate_name=candidate_name,
                    job_title=job_title,
                    application_id=application_id
                )
                logger.info(f"Email sent to recruiter {recruiter.email} for new application")
            except Exception as e:
                logger.error(f"Failed to send email to recruiter: {str(e)}")
        
        return notification

    @staticmethod
    def notify_status_update(
        db: Session,
        candidate_id: str,
        job_title: str,
        company_name: str,
        new_status: str,
        application_id: str
    ):
        # Get candidate email
        candidate = db.query(User).filter(User.id == candidate_id).first()
        
        status_messages = {
            'screening': 'is being reviewed',
            'shortlisted': 'has been shortlisted!',
            'interview_scheduled': 'interview has been scheduled',
            'interviewed': 'interview completed',
            'offer_extended': 'you received a job offer!',
            'offer_accepted': 'offer accepted - congratulations!',
            'rejected': 'was not selected',
            'withdrawn': 'has been withdrawn'
        }
        status_msg = status_messages.get(new_status, f'status changed to {new_status}')
        priority = 'high' if new_status in ['shortlisted', 'offer_extended'] else 'normal'
        
        # Create in-app notification
        notification = NotificationService.create_notification(
            db=db,
            user_id=candidate_id,
            notification_type='application_status_update',
            title=f'Application Update - {company_name}',
            message=f'Your application for {job_title} {status_msg}',
            action_url='/applications',
            priority=priority,
            metadata={'application_id': application_id, 'new_status': new_status},
            send_email=True
        )
        
        # Send email notification for important status changes
        email_statuses = ['shortlisted', 'interview_scheduled', 'offer_extended', 'rejected']
        if candidate and candidate.email and new_status in email_statuses:
            try:
                send_status_update_email(
                    candidate_email=candidate.email,
                    job_title=job_title,
                    company_name=company_name,
                    new_status=new_status,
                    application_id=application_id
                )
                logger.info(f"Email sent to candidate {candidate.email} for status: {new_status}")
            except Exception as e:
                logger.error(f"Failed to send email to candidate: {str(e)}")
        
        return notification


    # Job Expiring Notification
    @staticmethod
    def notify_job_expiring(
        db: Session,
        recruiter_id: str,
        job_id: str,
        job_title: str,
        company_name: str,
        days_remaining: int
    ):
        from app.services.email_service import send_job_expiring_email
        
        recruiter = db.query(User).filter(User.id == recruiter_id).first()
        
        notification = NotificationService.create_notification(
            db=db,
            user_id=recruiter_id,
            notification_type='job_expiring',
            title='Job Posting Expiring Soon',
            message=f'Your posting for {job_title} expires in {days_remaining} day{"s" if days_remaining > 1 else ""}',
            action_url=f'/recruiter/jobs/{job_id}/edit',
            priority='high' if days_remaining <= 1 else 'normal',
            metadata={'job_id': job_id, 'days_remaining': days_remaining},
            send_email=True
        )
        
        if recruiter and recruiter.email:
            try:
                send_job_expiring_email(
                    recruiter_email=recruiter.email,
                    job_title=job_title,
                    company_name=company_name,
                    days_remaining=days_remaining,
                    job_id=job_id
                )
                logger.info(f"Job expiring email sent to {recruiter.email}")
            except Exception as e:
                logger.error(f"Failed to send job expiring email: {str(e)}")
        
        return notification

    # New Job Match Notification
    @staticmethod
    def notify_job_match(
        db: Session,
        candidate_id: str,
        job_id: str,
        job_title: str,
        company_name: str,
        match_score: int
    ):
        from app.services.email_service import send_job_match_email
        
        candidate = db.query(User).filter(User.id == candidate_id).first()
        
        notification = NotificationService.create_notification(
            db=db,
            user_id=candidate_id,
            notification_type='job_match',
            title='New Job Match Found!',
            message=f'{job_title} at {company_name} is a {match_score}% match for your profile',
            action_url=f'/jobs/{job_id}',
            priority='high' if match_score >= 80 else 'normal',
            metadata={'job_id': job_id, 'match_score': match_score},
            send_email=True
        )
        
        # Only send email for high matches (80%+)
        if candidate and candidate.email and match_score >= 80:
            try:
                send_job_match_email(
                    candidate_email=candidate.email,
                    job_title=job_title,
                    company_name=company_name,
                    match_score=match_score,
                    job_id=job_id
                )
                logger.info(f"Job match email sent to {candidate.email}")
            except Exception as e:
                logger.error(f"Failed to send job match email: {str(e)}")
        
        return notification

    # Profile View Notification
    @staticmethod
    def notify_profile_view(
        db: Session,
        candidate_id: str,
        viewer_id: str,
        viewer_name: str,
        company_name: str
    ):
        from app.services.email_service import send_profile_view_email
        
        candidate = db.query(User).filter(User.id == candidate_id).first()
        
        notification = NotificationService.create_notification(
            db=db,
            user_id=candidate_id,
            notification_type='profile_view',
            title='Profile Viewed',
            message=f'{viewer_name} from {company_name} viewed your profile',
            action_url='/profile',
            priority='normal',
            metadata={'viewer_id': viewer_id, 'company_name': company_name},
            send_email=False  # Don't send email for every view
        )
        
        return notification

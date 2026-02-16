import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.from_email = os.getenv("EMAIL_FROM", self.smtp_user)
        self.from_name = os.getenv("EMAIL_FROM_NAME", "JobMatch AI")
        self.enabled = bool(self.smtp_user and self.smtp_password and self.smtp_password != "your_app_password_here")
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None
    ) -> bool:
        """Send an email to the specified recipient."""
        if not self.enabled:
            logger.warning(f"Email not sent (disabled): {subject} -> {to_email}")
            return False
        
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = to_email
            
            # Add plain text version
            if text_body:
                msg.attach(MIMEText(text_body, "plain"))
            
            # Add HTML version
            msg.attach(MIMEText(html_body, "html"))
            
            # Connect and send
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully: {subject} -> {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False
    
    def send_notification_email(
        self,
        to_email: str,
        notification_type: str,
        title: str,
        message: str,
        action_url: Optional[str] = None,
        priority: str = "normal"
    ) -> bool:
        """Send a notification email with a styled template."""
        
        priority_color = "#dc2626" if priority == "high" else "#2563eb"
        priority_badge = f'<span style="background-color: {priority_color}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px;">High Priority</span>' if priority == "high" else ""
        
        action_button = ""
        if action_url:
            full_url = f"http://localhost:3000{action_url}" if action_url.startswith("/") else action_url
            action_button = f'''
            <div style="margin-top: 24px;">
                <a href="{full_url}" style="background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block; font-weight: 500;">
                    View Details
                </a>
            </div>
            '''
        
        html_body = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #374151; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #2563eb; padding: 24px; border-radius: 8px 8px 0 0;">
                <h1 style="color: white; margin: 0; font-size: 24px;">JobMatch AI</h1>
            </div>
            <div style="background-color: #ffffff; padding: 32px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 8px 8px;">
                <div style="margin-bottom: 16px;">
                    {priority_badge}
                </div>
                <h2 style="color: #111827; margin: 0 0 16px 0; font-size: 20px;">
                    {title}
                </h2>
                <p style="color: #4b5563; margin: 0; font-size: 16px;">
                    {message}
                </p>
                {action_button}
            </div>
            <div style="text-align: center; padding: 24px; color: #9ca3af; font-size: 14px;">
                <p style="margin: 0;">You received this email because you have an account on JobMatch AI.</p>
                <p style="margin: 8px 0 0 0;">© 2026 JobMatch AI. All rights reserved.</p>
            </div>
        </body>
        </html>
        '''
        
        text_body = f"{title}\n\n{message}\n\nView details: http://localhost:3000{action_url}" if action_url else f"{title}\n\n{message}"
        
        return self.send_email(to_email, f"[JobMatch AI] {title}", html_body, text_body)


# Singleton instance
email_service = EmailService()


def send_application_received_email(
    recruiter_email: str,
    candidate_name: str,
    job_title: str,
    application_id: str
) -> bool:
    """Send email to recruiter when a candidate applies."""
    return email_service.send_notification_email(
        to_email=recruiter_email,
        notification_type="application_received",
        title="New Job Application",
        message=f"{candidate_name} has applied for the position of {job_title}. Review their application to proceed with the next steps.",
        action_url=f"/recruiter/applications/{application_id}",
        priority="normal"
    )


def send_status_update_email(
    candidate_email: str,
    job_title: str,
    company_name: str,
    new_status: str,
    application_id: str
) -> bool:
    """Send email to candidate when application status changes."""
    
    status_messages = {
        "screening": f"Your application for {job_title} at {company_name} is being reviewed.",
        "shortlisted": f"Great news! You have been shortlisted for {job_title} at {company_name}!",
        "interview_scheduled": f"Your interview for {job_title} at {company_name} has been scheduled.",
        "interviewed": f"Thank you for interviewing for {job_title} at {company_name}.",
        "offer_extended": f"Congratulations! You have received a job offer for {job_title} at {company_name}!",
        "offer_accepted": f"Congratulations on accepting the offer for {job_title} at {company_name}!",
        "rejected": f"Thank you for your interest in {job_title} at {company_name}. Unfortunately, we have decided to move forward with other candidates.",
        "withdrawn": f"Your application for {job_title} at {company_name} has been withdrawn.",
    }
    
    message = status_messages.get(new_status, f"Your application status for {job_title} at {company_name} has been updated to: {new_status}")
    
    priority = "high" if new_status in ["shortlisted", "offer_extended"] else "normal"
    
    return email_service.send_notification_email(
        to_email=candidate_email,
        notification_type="application_status_update",
        title=f"Application Update: {job_title}",
        message=message,
        action_url="/applications",
        priority=priority
    )


def send_job_expiring_email(
    recruiter_email: str,
    job_title: str,
    company_name: str,
    days_remaining: int,
    job_id: str
) -> bool:
    """Send email to recruiter when their job posting is expiring soon."""
    return email_service.send_notification_email(
        to_email=recruiter_email,
        notification_type="job_expiring",
        title=f"Job Posting Expiring Soon: {job_title}",
        message=f"Your job posting for {job_title} at {company_name} will expire in {days_remaining} day{'s' if days_remaining > 1 else ''}. Renew it to continue receiving applications.",
        action_url=f"/recruiter/jobs/{job_id}/edit",
        priority="high" if days_remaining <= 1 else "normal"
    )


def send_job_match_email(
    candidate_email: str,
    job_title: str,
    company_name: str,
    match_score: int,
    job_id: str
) -> bool:
    """Send email to candidate when a new matching job is found."""
    return email_service.send_notification_email(
        to_email=candidate_email,
        notification_type="job_match",
        title=f"New Job Match: {job_title}",
        message=f"We found a great match for you! {job_title} at {company_name} is a {match_score}% match for your profile. Check it out!",
        action_url=f"/jobs/{job_id}",
        priority="high" if match_score >= 80 else "normal"
    )


def send_profile_view_email(
    candidate_email: str,
    viewer_name: str,
    company_name: str
) -> bool:
    """Send email to candidate when a recruiter views their profile."""
    return email_service.send_notification_email(
        to_email=candidate_email,
        notification_type="profile_view",
        title="Someone Viewed Your Profile",
        message=f"{viewer_name} from {company_name} viewed your profile. Keep your profile updated to attract more opportunities!",
        action_url="/profile",
        priority="normal"
    )

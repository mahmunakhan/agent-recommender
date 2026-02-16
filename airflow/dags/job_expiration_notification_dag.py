"""
DAG 6: Job Expiration & Notifications Pipeline
Checks for expiring jobs and sends notifications.
Runs every 6 hours.
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
import sys
import os
import uuid

sys.path.insert(0, '/opt/airflow')

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

def get_db_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    db_url = os.getenv('APP_DATABASE_URL')
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    return Session()

def check_expiring_jobs(**context):
    """Check for jobs expiring soon and notify recruiters"""
    from sqlalchemy import text
    
    db = get_db_session()
    notifications_sent = 0
    
    try:
        # Find jobs expiring in 1, 3, or 7 days
        for days in [7, 3, 1]:
            result = db.execute(text("""
                SELECT j.id, j.title, j.company_name, j.posted_by, j.expires_at
                FROM jobs j
                WHERE j.is_active = TRUE
                AND j.expires_at IS NOT NULL
                AND j.expires_at BETWEEN NOW() AND DATE_ADD(NOW(), INTERVAL :days DAY)
                AND j.expires_at > DATE_ADD(NOW(), INTERVAL :days_minus DAY)
            """), {'days': days, 'days_minus': days - 1})
            
            jobs = list(result)
            
            for job in jobs:
                job_id, title, company, recruiter_id, expires_at = job
                
                if not recruiter_id:
                    continue
                
                # Check if notification already sent
                existing = db.execute(text("""
                    SELECT 1 FROM notifications 
                    WHERE user_id = :user_id 
                    AND notification_type = 'job_expiring'
                    AND JSON_EXTRACT(metadata, '$.job_id') = :job_id
                    AND created_at > DATE_SUB(NOW(), INTERVAL 1 DAY)
                """), {'user_id': recruiter_id, 'job_id': job_id}).fetchone()
                
                if existing:
                    continue
                
                # Create notification
                priority = 'high' if days <= 1 else 'medium' if days <= 3 else 'normal'
                
                db.execute(text("""
                    INSERT INTO notifications
                    (id, user_id, notification_type, title, message, priority, channels, metadata, created_at)
                    VALUES
                    (:id, :user_id, 'job_expiring', :title, :message, :priority, '["in_app", "email"]', :metadata, NOW())
                """), {
                    'id': str(uuid.uuid4()),
                    'user_id': recruiter_id,
                    'title': f'Job Expiring in {days} Day{"s" if days > 1 else ""}',
                    'message': f'Your job posting "{title}" at {company} will expire soon.',
                    'priority': priority,
                    'metadata': f'{{"job_id": "{job_id}", "days_remaining": {days}}}'
                })
                
                notifications_sent += 1
            
            db.commit()
        
        print(f"Sent {notifications_sent} expiration notifications")
        return notifications_sent
        
    finally:
        db.close()

def deactivate_expired_jobs(**context):
    """Deactivate jobs that have expired"""
    from sqlalchemy import text
    
    db = get_db_session()
    
    try:
        result = db.execute(text("""
            UPDATE jobs 
            SET is_active = FALSE, updated_at = NOW()
            WHERE is_active = TRUE 
            AND expires_at IS NOT NULL 
            AND expires_at < NOW()
        """))
        
        db.commit()
        count = result.rowcount
        print(f"Deactivated {count} expired jobs")
        return count
        
    finally:
        db.close()

def send_job_match_notifications(**context):
    """Send notifications for new job matches"""
    from sqlalchemy import text
    
    db = get_db_session()
    notifications_sent = 0
    
    try:
        # Find new jobs posted in last 6 hours
        result = db.execute(text("""
            SELECT j.id, j.title, j.company_name
            FROM jobs j
            WHERE j.is_active = TRUE
            AND j.posted_at > DATE_SUB(NOW(), INTERVAL 6 HOUR)
        """))
        
        new_jobs = list(result)
        
        for job in new_jobs:
            job_id, title, company = job
            
            # Get job skills
            skills_result = db.execute(text("""
                SELECT skill_id FROM job_skills WHERE job_id = :job_id
            """), {'job_id': job_id})
            job_skill_ids = {row[0] for row in skills_result}
            
            if not job_skill_ids:
                continue
            
            # Find matching candidates
            candidates_result = db.execute(text("""
                SELECT DISTINCT p.user_id
                FROM profiles p
                JOIN profile_skills ps ON p.id = ps.profile_id
                WHERE p.is_verified = TRUE
                AND p.is_open_to_work = TRUE
                AND ps.skill_id IN :skills
                GROUP BY p.user_id
                HAVING COUNT(DISTINCT ps.skill_id) >= :min_match
            """), {'skills': tuple(job_skill_ids), 'min_match': max(1, len(job_skill_ids) // 2)})
            
            for candidate in candidates_result:
                user_id = candidate[0]
                
                # Check if already notified
                existing = db.execute(text("""
                    SELECT 1 FROM notifications 
                    WHERE user_id = :user_id 
                    AND notification_type = 'job_match'
                    AND JSON_EXTRACT(metadata, '$.job_id') = :job_id
                """), {'user_id': user_id, 'job_id': job_id}).fetchone()
                
                if existing:
                    continue
                
                db.execute(text("""
                    INSERT INTO notifications
                    (id, user_id, notification_type, title, message, priority, channels, metadata, created_at)
                    VALUES
                    (:id, :user_id, 'job_match', :title, :message, 'normal', '["in_app"]', :metadata, NOW())
                """), {
                    'id': str(uuid.uuid4()),
                    'user_id': user_id,
                    'title': 'New Job Match',
                    'message': f'A new job matching your skills: {title} at {company}',
                    'metadata': f'{{"job_id": "{job_id}"}}'
                })
                
                notifications_sent += 1
        
        db.commit()
        print(f"Sent {notifications_sent} job match notifications")
        return notifications_sent
        
    finally:
        db.close()

with DAG(
    'job_expiration_notification_pipeline',
    default_args=default_args,
    description='Check expiring jobs and send notifications',
    schedule_interval='0 */6 * * *',
    start_date=days_ago(1),
    catchup=False,
    tags=['jobs', 'notifications', 'expiration'],
) as dag:

    check_task = PythonOperator(
        task_id='check_expiring_jobs',
        python_callable=check_expiring_jobs,
    )

    deactivate_task = PythonOperator(
        task_id='deactivate_expired_jobs',
        python_callable=deactivate_expired_jobs,
    )

    match_task = PythonOperator(
        task_id='send_job_match_notifications',
        python_callable=send_job_match_notifications,
    )

    check_task >> deactivate_task >> match_task

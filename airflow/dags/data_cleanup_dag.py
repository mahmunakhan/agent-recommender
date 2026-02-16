"""
DAG 9: Data Cleanup Pipeline
Cleans up old data, expired records, and maintains database health.
Runs daily.
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
import sys
import os

sys.path.insert(0, '/opt/airflow')

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

def get_db_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    db_url = os.getenv('APP_DATABASE_URL')
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    return Session()

def cleanup_old_recommendations(**context):
    """Remove recommendations older than 30 days"""
    from sqlalchemy import text
    
    db = get_db_session()
    
    try:
        result = db.execute(text("""
            DELETE FROM recommendations 
            WHERE created_at < DATE_SUB(NOW(), INTERVAL 30 DAY)
        """))
        db.commit()
        
        count = result.rowcount
        print(f"Deleted {count} old recommendations")
        return count
        
    finally:
        db.close()

def cleanup_old_notifications(**context):
    """Remove read notifications older than 60 days"""
    from sqlalchemy import text
    
    db = get_db_session()
    
    try:
        result = db.execute(text("""
            DELETE FROM notifications 
            WHERE is_read = TRUE 
            AND created_at < DATE_SUB(NOW(), INTERVAL 60 DAY)
        """))
        db.commit()
        
        count = result.rowcount
        print(f"Deleted {count} old notifications")
        return count
        
    finally:
        db.close()

def cleanup_expired_jobs(**context):
    """Archive jobs expired more than 90 days ago"""
    from sqlalchemy import text
    
    db = get_db_session()
    
    try:
        # Deactivate old expired jobs
        result = db.execute(text("""
            UPDATE jobs 
            SET is_active = FALSE 
            WHERE expires_at < DATE_SUB(NOW(), INTERVAL 90 DAY)
            AND is_active = TRUE
        """))
        db.commit()
        
        count = result.rowcount
        print(f"Archived {count} expired jobs")
        return count
        
    finally:
        db.close()

def cleanup_orphaned_records(**context):
    """Clean up orphaned records"""
    from sqlalchemy import text
    
    db = get_db_session()
    
    try:
        # Clean orphaned job_skills
        db.execute(text("""
            DELETE js FROM job_skills js
            LEFT JOIN jobs j ON js.job_id = j.id
            WHERE j.id IS NULL
        """))
        
        # Clean orphaned profile_skills
        db.execute(text("""
            DELETE ps FROM profile_skills ps
            LEFT JOIN profiles p ON ps.profile_id = p.id
            WHERE p.id IS NULL
        """))
        
        # Clean addressed skill gaps older than 90 days
        db.execute(text("""
            DELETE FROM skill_gaps 
            WHERE is_addressed = TRUE 
            AND addressed_at < DATE_SUB(NOW(), INTERVAL 90 DAY)
        """))
        
        db.commit()
        print("Orphaned records cleaned")
        return True
        
    finally:
        db.close()

def optimize_tables(**context):
    """Optimize database tables"""
    from sqlalchemy import text
    
    db = get_db_session()
    
    try:
        tables = ['jobs', 'profiles', 'recommendations', 'notifications', 'skill_gaps']
        
        for table in tables:
            try:
                db.execute(text(f"OPTIMIZE TABLE {table}"))
                print(f"Optimized table: {table}")
            except Exception as e:
                print(f"Could not optimize {table}: {str(e)}")
        
        db.commit()
        return True
        
    finally:
        db.close()

with DAG(
    'data_cleanup_pipeline',
    default_args=default_args,
    description='Clean up old data and optimize database',
    schedule_interval='0 2 * * *',  # Daily at 2 AM
    start_date=days_ago(1),
    catchup=False,
    tags=['cleanup', 'maintenance', 'database'],
) as dag:

    rec_cleanup = PythonOperator(
        task_id='cleanup_old_recommendations',
        python_callable=cleanup_old_recommendations,
    )

    notif_cleanup = PythonOperator(
        task_id='cleanup_old_notifications',
        python_callable=cleanup_old_notifications,
    )

    job_cleanup = PythonOperator(
        task_id='cleanup_expired_jobs',
        python_callable=cleanup_expired_jobs,
    )

    orphan_cleanup = PythonOperator(
        task_id='cleanup_orphaned_records',
        python_callable=cleanup_orphaned_records,
    )

    optimize = PythonOperator(
        task_id='optimize_tables',
        python_callable=optimize_tables,
    )

    [rec_cleanup, notif_cleanup, job_cleanup] >> orphan_cleanup >> optimize

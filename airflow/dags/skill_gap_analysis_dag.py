"""
DAG 5: Skill Gap Analysis Pipeline
Analyzes skill gaps for candidates based on their recommendations.
Runs every 6 hours.
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
import sys
import os
import json
import uuid

sys.path.insert(0, '/opt/airflow')

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}

def get_db_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    db_url = os.getenv('APP_DATABASE_URL')
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    return Session()

def analyze_skill_gaps(**context):
    """Analyze skill gaps for all candidates with recommendations"""
    from sqlalchemy import text
    
    db = get_db_session()
    
    try:
        # Get users with recommendations
        users_result = db.execute(text("""
            SELECT DISTINCT r.user_id
            FROM recommendations r
            JOIN users u ON r.user_id = u.id
            WHERE u.is_active = TRUE
        """))
        
        users = [row[0] for row in users_result]
        print(f"Analyzing skill gaps for {len(users)} users")
        
        total_gaps = 0
        
        for user_id in users:
            # Get missing skills from top recommendations
            missing_result = db.execute(text("""
                SELECT missing_skills
                FROM recommendations
                WHERE user_id = :user_id
                ORDER BY match_score DESC
                LIMIT 10
            """), {'user_id': user_id})
            
            # Aggregate missing skills
            skill_frequency = {}
            for row in missing_result:
                if row[0]:
                    missing = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                    for skill_id in missing.get('skill_ids', []):
                        skill_frequency[skill_id] = skill_frequency.get(skill_id, 0) + 1
            
            # Get user's current skills
            current_result = db.execute(text("""
                SELECT ps.skill_id, ps.proficiency_level
                FROM profile_skills ps
                JOIN profiles p ON ps.profile_id = p.id
                WHERE p.user_id = :user_id
            """), {'user_id': user_id})
            
            current_skills = {row[0]: row[1] for row in current_result}
            
            # Clear old unaddressed gaps
            db.execute(text("""
                DELETE FROM skill_gaps 
                WHERE user_id = :user_id AND is_addressed = FALSE
            """), {'user_id': user_id})
            
            # Create new skill gaps
            for skill_id, frequency in sorted(skill_frequency.items(), key=lambda x: -x[1])[:10]:
                if skill_id not in current_skills:
                    gap_type = 'missing'
                    current_level = 'none'
                else:
                    gap_type = 'insufficient'
                    current_level = current_skills[skill_id]
                
                priority_score = min(100, frequency * 15)
                
                db.execute(text("""
                    INSERT INTO skill_gaps 
                    (id, user_id, skill_id, gap_type, current_level, target_level, 
                     priority_score, frequency_in_jobs, source, is_addressed, created_at, updated_at)
                    VALUES 
                    (:id, :user_id, :skill_id, :gap_type, :current_level, 'intermediate',
                     :priority, :frequency, 'job_matching', FALSE, NOW(), NOW())
                """), {
                    'id': str(uuid.uuid4()),
                    'user_id': user_id,
                    'skill_id': skill_id,
                    'gap_type': gap_type,
                    'current_level': current_level,
                    'priority': priority_score,
                    'frequency': frequency
                })
                total_gaps += 1
            
            db.commit()
            
        print(f"Created {total_gaps} skill gaps")
        return total_gaps
        
    except Exception as e:
        print(f"Error: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

with DAG(
    'skill_gap_analysis_pipeline',
    default_args=default_args,
    description='Analyze skill gaps for candidates',
    schedule_interval='0 */6 * * *',
    start_date=days_ago(1),
    catchup=False,
    tags=['skills', 'gap-analysis', 'ai'],
) as dag:

    analyze_task = PythonOperator(
        task_id='analyze_skill_gaps',
        python_callable=analyze_skill_gaps,
    )

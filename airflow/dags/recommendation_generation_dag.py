"""
DAG 4: Recommendation Generation Pipeline
Generates job recommendations for all active candidates.
Runs every 6 hours.
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
import sys
import os
import json

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

def fetch_active_candidates(**context):
    """Fetch candidates who need recommendations"""
    from sqlalchemy import text
    
    db = get_db_session()
    try:
        result = db.execute(text("""
            SELECT p.id, p.user_id, p.headline, p.location_city, p.years_experience, p.desired_role
            FROM profiles p
            JOIN users u ON p.user_id = u.id
            WHERE p.is_verified = TRUE
            AND p.is_open_to_work = TRUE
            AND u.is_active = TRUE
            AND u.role = 'candidate'
            LIMIT 100
        """))
        
        candidates = [{
            'profile_id': row[0], 
            'user_id': row[1], 
            'headline': row[2],
            'location': row[3],
            'experience': row[4],
            'desired_role': row[5]
        } for row in result]
        
        print(f"Found {len(candidates)} active candidates")
        context['task_instance'].xcom_push(key='candidates', value=candidates)
        return len(candidates)
    finally:
        db.close()

def generate_recommendations(**context):
    """Generate recommendations for each candidate"""
    from sqlalchemy import text
    import uuid
    
    candidates = context['task_instance'].xcom_pull(key='candidates', task_ids='fetch_active_candidates')
    if not candidates:
        return 0
    
    db = get_db_session()
    total_recs = 0
    
    for candidate in candidates:
        try:
            # Get candidate skills
            skills_result = db.execute(text("""
                SELECT skill_id FROM profile_skills WHERE profile_id = :profile_id
            """), {'profile_id': candidate['profile_id']})
            user_skill_ids = {row[0] for row in skills_result}
            
            # Get active jobs
            jobs_result = db.execute(text("""
                SELECT j.id, j.title, j.company_name, j.location_city, j.location_type,
                       j.experience_min_years, j.salary_min, j.salary_max
                FROM jobs j
                WHERE j.is_active = TRUE
                AND (j.expires_at IS NULL OR j.expires_at > NOW())
                ORDER BY j.posted_at DESC
                LIMIT 100
            """))
            
            jobs = list(jobs_result)
            scored_jobs = []
            batch_id = str(uuid.uuid4())
            
            for job in jobs:
                job_id = job[0]
                
                # Get job skills
                job_skills_result = db.execute(text("""
                    SELECT skill_id, requirement_type FROM job_skills WHERE job_id = :job_id
                """), {'job_id': job_id})
                job_skills = list(job_skills_result)
                job_skill_ids = {row[0] for row in job_skills}
                required_skills = {row[0] for row in job_skills if row[1] == 'required'}
                
                # Calculate skill match
                if job_skill_ids:
                    matched = user_skill_ids & job_skill_ids
                    skill_score = (len(matched) / len(job_skill_ids)) * 100
                else:
                    skill_score = 50
                
                # Calculate experience match
                exp_score = 100
                job_min_exp = job[5] or 0
                user_exp = candidate['experience'] or 0
                if job_min_exp > 0:
                    if user_exp >= job_min_exp:
                        exp_score = 100
                    else:
                        gap = job_min_exp - user_exp
                        exp_score = max(0, 100 - (gap * 20))
                
                # Calculate location match
                loc_score = 100
                if job[4] == 'remote':
                    loc_score = 100
                elif candidate['location'] and job[3]:
                    if candidate['location'].lower() == job[3].lower():
                        loc_score = 100
                    else:
                        loc_score = 50
                
                # Overall score
                match_score = (skill_score * 0.4) + (exp_score * 0.3) + (loc_score * 0.3)
                
                scored_jobs.append({
                    'job_id': job_id,
                    'match_score': match_score,
                    'skill_score': skill_score,
                    'exp_score': exp_score,
                    'loc_score': loc_score,
                    'matched_skills': list(user_skill_ids & job_skill_ids),
                    'missing_skills': list(required_skills - user_skill_ids)
                })
            
            # Sort and save top recommendations
            scored_jobs.sort(key=lambda x: x['match_score'], reverse=True)
            
            # Delete old recommendations
            db.execute(text("""
                DELETE FROM recommendations WHERE user_id = :user_id
            """), {'user_id': candidate['user_id']})
            
            # Insert new recommendations
            for rank, scored in enumerate(scored_jobs[:20], 1):
                db.execute(text("""
                    INSERT INTO recommendations 
                    (user_id, job_id, batch_id, match_score, skill_match_score, 
                     experience_match_score, location_match_score, semantic_similarity,
                     ranking_position, matched_skills, missing_skills, is_viewed, created_at)
                    VALUES 
                    (:user_id, :job_id, :batch_id, :match_score, :skill_score,
                     :exp_score, :loc_score, 0.5,
                     :rank, :matched, :missing, FALSE, NOW())
                """), {
                    'user_id': candidate['user_id'],
                    'job_id': scored['job_id'],
                    'batch_id': batch_id,
                    'match_score': scored['match_score'],
                    'skill_score': scored['skill_score'],
                    'exp_score': scored['exp_score'],
                    'loc_score': scored['loc_score'],
                    'rank': rank,
                    'matched': json.dumps({'skill_ids': scored['matched_skills'][:5]}),
                    'missing': json.dumps({'skill_ids': scored['missing_skills'][:5]})
                })
            
            db.commit()
            total_recs += min(len(scored_jobs), 20)
            print(f"Generated {min(len(scored_jobs), 20)} recommendations for user {candidate['user_id']}")
            
        except Exception as e:
            print(f"Error processing candidate {candidate['user_id']}: {str(e)}")
            db.rollback()
            continue
    
    db.close()
    return total_recs

with DAG(
    'recommendation_generation_pipeline',
    default_args=default_args,
    description='Generate job recommendations for candidates',
    schedule_interval='0 */6 * * *',
    start_date=days_ago(1),
    catchup=False,
    tags=['recommendations', 'matching', 'ai'],
) as dag:

    fetch_task = PythonOperator(
        task_id='fetch_active_candidates',
        python_callable=fetch_active_candidates,
    )

    generate_task = PythonOperator(
        task_id='generate_recommendations',
        python_callable=generate_recommendations,
    )

    fetch_task >> generate_task

"""
DAG 2: Job Processing Pipeline
Processes new jobs - extracts skills, generates embeddings.
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

def fetch_unprocessed_jobs(**context):
    """Fetch jobs without skill extraction"""
    from sqlalchemy import text
    
    db = get_db_session()
    try:
        result = db.execute(text("""
            SELECT j.id, j.title, j.description_raw, j.company_name
            FROM jobs j
            LEFT JOIN job_skills js ON j.id = js.job_id
            WHERE j.is_active = TRUE
            AND js.job_id IS NULL
            LIMIT 100
        """))
        
        jobs = [{'id': row[0], 'title': row[1], 'description': row[2], 'company': row[3]} for row in result]
        print(f"Found {len(jobs)} jobs without skills")
        context['task_instance'].xcom_push(key='jobs', value=jobs)
        return len(jobs)
    finally:
        db.close()

def extract_job_skills(**context):
    """Extract skills from job descriptions using AI"""
    from groq import Groq
    from sqlalchemy import text
    import re
    
    jobs = context['task_instance'].xcom_pull(key='jobs', task_ids='fetch_unprocessed_jobs')
    if not jobs:
        return 0
    
    db = get_db_session()
    groq_client = Groq(api_key=os.getenv('GROQ_API_KEY'))
    
    # Get all skills for matching
    skills_result = db.execute(text("SELECT id, name, slug FROM skills"))
    all_skills = {row[1].lower(): row[0] for row in skills_result}
    
    processed = 0
    
    for job in jobs:
        try:
            system_prompt = """Extract technical skills from this job description.
Return ONLY a JSON array of skill names like: ["Python", "Docker", "AWS", "React"]
Include only specific technical skills, tools, frameworks, and technologies."""

            response = groq_client.chat.completions.create(
                model="llama-3.1-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Job: {job['title']}\n\n{job['description'][:4000]}"}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            skills_text = response.choices[0].message.content
            json_match = re.search(r'\[[\s\S]*?\]', skills_text)
            
            if json_match:
                extracted_skills = json.loads(json_match.group())
                
                for skill_name in extracted_skills[:15]:
                    skill_lower = skill_name.lower().strip()
                    
                    if skill_lower in all_skills:
                        skill_id = all_skills[skill_lower]
                        
                        # Check if already exists
                        exists = db.execute(text("""
                            SELECT 1 FROM job_skills WHERE job_id = :job_id AND skill_id = :skill_id
                        """), {'job_id': job['id'], 'skill_id': skill_id}).fetchone()
                        
                        if not exists:
                            db.execute(text("""
                                INSERT INTO job_skills (id, job_id, skill_id, requirement_type, importance_score)
                                VALUES (UUID(), :job_id, :skill_id, 'required', 0.8)
                            """), {'job_id': job['id'], 'skill_id': skill_id})
                
                db.commit()
                processed += 1
                print(f"Extracted skills for job {job['id']}: {len(extracted_skills)} skills")
                
        except Exception as e:
            print(f"Error processing job {job['id']}: {str(e)}")
            continue
    
    db.close()
    return processed

with DAG(
    'job_processing_pipeline',
    default_args=default_args,
    description='Process jobs and extract skills',
    schedule_interval='0 */6 * * *',
    start_date=days_ago(1),
    catchup=False,
    tags=['job', 'skills', 'processing'],
) as dag:

    fetch_task = PythonOperator(
        task_id='fetch_unprocessed_jobs',
        python_callable=fetch_unprocessed_jobs,
    )

    extract_task = PythonOperator(
        task_id='extract_job_skills',
        python_callable=extract_job_skills,
    )

    fetch_task >> extract_task

"""
DAG 1: Resume Processing Pipeline
Processes uploaded resumes that haven't been parsed yet.
Runs every 6 hours.
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
import sys
import os

# Add app to path
sys.path.insert(0, '/opt/airflow')

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}

def get_db_session():
    """Get database session"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    db_url = os.getenv('APP_DATABASE_URL')
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    return Session()

def fetch_unprocessed_resumes(**context):
    """Fetch profiles with resumes that need processing"""
    from sqlalchemy import select, text
    
    db = get_db_session()
    try:
        result = db.execute(text("""
            SELECT p.id, p.user_id, p.resume_s3_path 
            FROM profiles p 
            WHERE p.resume_s3_path IS NOT NULL 
            AND p.is_verified = FALSE 
            AND (p.parsed_json_draft IS NULL OR p.parsed_json_draft = '{}')
            LIMIT 50
        """))
        
        profiles = [{'id': row[0], 'user_id': row[1], 'resume_path': row[2]} for row in result]
        print(f"Found {len(profiles)} unprocessed resumes")
        
        context['task_instance'].xcom_push(key='profiles', value=profiles)
        return len(profiles)
    finally:
        db.close()

def process_resumes(**context):
    """Process each resume using AI parser"""
    from groq import Groq
    import json
    from sqlalchemy import text
    from minio import Minio
    import fitz  # PyMuPDF
    import io
    
    profiles = context['task_instance'].xcom_pull(key='profiles', task_ids='fetch_unprocessed_resumes')
    
    if not profiles:
        print("No profiles to process")
        return 0
    
    db = get_db_session()
    groq_client = Groq(api_key=os.getenv('GROQ_API_KEY'))
    
    minio_client = Minio(
        os.getenv('MINIO_ENDPOINT'),
        access_key=os.getenv('MINIO_ACCESS_KEY'),
        secret_key=os.getenv('MINIO_SECRET_KEY'),
        secure=False
    )
    
    processed = 0
    
    for profile in profiles:
        try:
            # Download resume from MinIO
            bucket = 'resumes'
            object_name = profile['resume_path'].replace('resumes/', '')
            
            response = minio_client.get_object(bucket, object_name)
            pdf_bytes = response.read()
            response.close()
            
            # Extract text from PDF
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            text_content = ""
            for page in doc:
                text_content += page.get_text()
            doc.close()
            
            # Parse with AI
            system_prompt = """You are a resume parser. Extract structured data from resumes.
Return ONLY valid JSON with this structure:
{
    "personal_info": {"name": "", "email": "", "phone": "", "linkedin": ""},
    "headline": "",
    "summary": "",
    "location": {"city": "", "country": ""},
    "years_experience": 0,
    "education": [{"institution": "", "degree": "", "field": "", "year": 0}],
    "experience": [{"company": "", "title": "", "duration": "", "description": ""}],
    "skills": [{"name": "", "proficiency": "intermediate"}],
    "certifications": [{"name": "", "issuer": "", "year": 0}]
}"""

            response = groq_client.chat.completions.create(
                model="llama-3.1-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Parse this resume:\n\n{text_content[:8000]}"}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            parsed_text = response.choices[0].message.content
            
            # Extract JSON
            import re
            json_match = re.search(r'\{[\s\S]*\}', parsed_text)
            if json_match:
                parsed_json = json.loads(json_match.group())
                
                # Update profile
                db.execute(text("""
                    UPDATE profiles 
                    SET resume_text_extracted = :text,
                        parsed_json_draft = :parsed,
                        headline = :headline,
                        summary = :summary,
                        location_city = :city,
                        location_country = :country,
                        years_experience = :years,
                        updated_at = NOW()
                    WHERE id = :profile_id
                """), {
                    'text': text_content[:10000],
                    'parsed': json.dumps(parsed_json),
                    'headline': parsed_json.get('headline', ''),
                    'summary': parsed_json.get('summary', ''),
                    'city': parsed_json.get('location', {}).get('city', ''),
                    'country': parsed_json.get('location', {}).get('country', ''),
                    'years': parsed_json.get('years_experience', 0),
                    'profile_id': profile['id']
                })
                db.commit()
                processed += 1
                print(f"Processed profile {profile['id']}")
                
        except Exception as e:
            print(f"Error processing profile {profile['id']}: {str(e)}")
            continue
    
    db.close()
    print(f"Processed {processed} resumes")
    return processed

def update_processing_stats(**context):
    """Update processing statistics"""
    processed = context['task_instance'].xcom_pull(task_ids='process_resumes')
    print(f"Resume processing complete. Processed: {processed}")

with DAG(
    'resume_processing_pipeline',
    default_args=default_args,
    description='Process uploaded resumes with AI parsing',
    schedule_interval='0 */6 * * *',  # Every 6 hours
    start_date=days_ago(1),
    catchup=False,
    tags=['resume', 'ai', 'processing'],
) as dag:

    fetch_task = PythonOperator(
        task_id='fetch_unprocessed_resumes',
        python_callable=fetch_unprocessed_resumes,
    )

    process_task = PythonOperator(
        task_id='process_resumes',
        python_callable=process_resumes,
    )

    stats_task = PythonOperator(
        task_id='update_processing_stats',
        python_callable=update_processing_stats,
    )

    fetch_task >> process_task >> stats_task

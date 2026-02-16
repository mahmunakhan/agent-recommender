"""
DAG 3: Embedding Generation Pipeline
Generates embeddings for profiles and jobs that need vectorization.
Runs every 6 hours.
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

def get_milvus_client():
    from pymilvus import connections, Collection
    connections.connect(
        alias="default",
        host=os.getenv('MILVUS_HOST', 'localhost'),
        port=os.getenv('MILVUS_PORT', '19530')
    )
    return True

def generate_profile_embeddings(**context):
    """Generate embeddings for verified profiles"""
    from sqlalchemy import text
    from groq import Groq
    from pymilvus import Collection
    import numpy as np
    
    db = get_db_session()
    get_milvus_client()
    groq_client = Groq(api_key=os.getenv('GROQ_API_KEY'))
    
    # Get profiles needing vectorization
    result = db.execute(text("""
        SELECT id, user_id, headline, summary, validated_json
        FROM profiles
        WHERE is_verified = TRUE
        AND (last_vectorized_at IS NULL OR last_vectorized_at < updated_at)
        LIMIT 50
    """))
    
    profiles = [{'id': row[0], 'user_id': row[1], 'headline': row[2], 'summary': row[3], 'json': row[4]} for row in result]
    print(f"Found {len(profiles)} profiles to vectorize")
    
    collection = Collection("profile_embeddings")
    processed = 0
    
    for profile in profiles:
        try:
            # Create text for embedding
            text_content = f"{profile['headline'] or ''} {profile['summary'] or ''}"
            if profile['json']:
                import json
                data = json.loads(profile['json']) if isinstance(profile['json'], str) else profile['json']
                skills = [s.get('name', '') for s in data.get('skills', [])]
                text_content += " " + " ".join(skills)
            
            # Generate embedding using Groq (or use sentence-transformers)
            response = groq_client.chat.completions.create(
                model="llama-3.1-70b-versatile",
                messages=[
                    {"role": "system", "content": "Generate a semantic summary of this profile in exactly 50 words focusing on skills and experience."},
                    {"role": "user", "content": text_content[:2000]}
                ],
                temperature=0.1,
                max_tokens=100
            )
            summary_text = response.choices[0].message.content
            
            # For actual embeddings, we'd use sentence-transformers
            # Here we'll generate a simple hash-based vector for demo
            import hashlib
            hash_val = hashlib.sha256(summary_text.encode()).hexdigest()
            embedding = [float(int(hash_val[i:i+2], 16))/255.0 for i in range(0, 128, 2)]
            embedding = embedding * 24  # Expand to 1536 dimensions
            embedding = embedding[:1536]
            
            # Upsert to Milvus
            collection.upsert([[profile['id']], [embedding]])
            
            # Update profile
            db.execute(text("""
                UPDATE profiles SET last_vectorized_at = NOW() WHERE id = :id
            """), {'id': profile['id']})
            db.commit()
            
            processed += 1
            
        except Exception as e:
            print(f"Error processing profile {profile['id']}: {str(e)}")
            continue
    
    db.close()
    context['task_instance'].xcom_push(key='profiles_processed', value=processed)
    return processed

def generate_job_embeddings(**context):
    """Generate embeddings for jobs"""
    from sqlalchemy import text
    from groq import Groq
    from pymilvus import Collection
    
    db = get_db_session()
    get_milvus_client()
    groq_client = Groq(api_key=os.getenv('GROQ_API_KEY'))
    
    result = db.execute(text("""
        SELECT id, title, description_raw, company_name
        FROM jobs
        WHERE is_active = TRUE
        AND (last_vectorized_at IS NULL OR last_vectorized_at < updated_at)
        LIMIT 100
    """))
    
    jobs = [{'id': row[0], 'title': row[1], 'description': row[2], 'company': row[3]} for row in result]
    print(f"Found {len(jobs)} jobs to vectorize")
    
    collection = Collection("job_embeddings")
    processed = 0
    
    for job in jobs:
        try:
            text_content = f"{job['title']} at {job['company']}. {job['description'][:2000]}"
            
            import hashlib
            hash_val = hashlib.sha256(text_content.encode()).hexdigest()
            embedding = [float(int(hash_val[i:i+2], 16))/255.0 for i in range(0, 128, 2)]
            embedding = embedding * 24
            embedding = embedding[:1536]
            
            collection.upsert([[job['id']], [embedding]])
            
            db.execute(text("""
                UPDATE jobs SET last_vectorized_at = NOW() WHERE id = :id
            """), {'id': job['id']})
            db.commit()
            
            processed += 1
            
        except Exception as e:
            print(f"Error processing job {job['id']}: {str(e)}")
            continue
    
    db.close()
    context['task_instance'].xcom_push(key='jobs_processed', value=processed)
    return processed

with DAG(
    'embedding_generation_pipeline',
    default_args=default_args,
    description='Generate embeddings for profiles and jobs',
    schedule_interval='0 */6 * * *',
    start_date=days_ago(1),
    catchup=False,
    tags=['embedding', 'milvus', 'vectorization'],
) as dag:

    profile_task = PythonOperator(
        task_id='generate_profile_embeddings',
        python_callable=generate_profile_embeddings,
    )

    job_task = PythonOperator(
        task_id='generate_job_embeddings',
        python_callable=generate_job_embeddings,
    )

    profile_task >> job_task

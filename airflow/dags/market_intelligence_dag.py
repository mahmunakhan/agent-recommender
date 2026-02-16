"""
DAG 8: Market Intelligence Pipeline
Analyzes job market trends and updates skill popularity.
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

def analyze_skill_demand(**context):
    """Analyze skill demand from job postings"""
    from sqlalchemy import text
    
    db = get_db_session()
    
    try:
        # Count skill occurrences in active jobs
        result = db.execute(text("""
            SELECT js.skill_id, s.name, COUNT(*) as job_count,
                   AVG(j.salary_max) as avg_salary
            FROM job_skills js
            JOIN skills s ON js.skill_id = s.id
            JOIN jobs j ON js.job_id = j.id
            WHERE j.is_active = TRUE
            AND j.posted_at > DATE_SUB(NOW(), INTERVAL 30 DAY)
            GROUP BY js.skill_id, s.name
            ORDER BY job_count DESC
        """))
        
        skills = list(result)
        print(f"Analyzed demand for {len(skills)} skills")
        
        # Update skill popularity scores
        max_count = skills[0][2] if skills else 1
        
        for skill in skills:
            skill_id, name, count, avg_salary = skill
            popularity = (count / max_count) * 100
            
            db.execute(text("""
                UPDATE skills 
                SET popularity_score = :popularity,
                    updated_at = NOW()
                WHERE id = :skill_id
            """), {'popularity': popularity, 'skill_id': skill_id})
        
        db.commit()
        context['task_instance'].xcom_push(key='skills_analyzed', value=len(skills))
        return len(skills)
        
    finally:
        db.close()

def identify_trending_skills(**context):
    """Identify skills with growing demand"""
    from sqlalchemy import text
    
    db = get_db_session()
    
    try:
        # Compare last 7 days vs previous 7 days
        result = db.execute(text("""
            SELECT 
                s.id,
                s.name,
                COUNT(CASE WHEN j.posted_at > DATE_SUB(NOW(), INTERVAL 7 DAY) THEN 1 END) as recent_count,
                COUNT(CASE WHEN j.posted_at BETWEEN DATE_SUB(NOW(), INTERVAL 14 DAY) AND DATE_SUB(NOW(), INTERVAL 7 DAY) THEN 1 END) as prev_count
            FROM skills s
            LEFT JOIN job_skills js ON s.id = js.skill_id
            LEFT JOIN jobs j ON js.job_id = j.id AND j.is_active = TRUE
            GROUP BY s.id, s.name
            HAVING recent_count > 0 OR prev_count > 0
        """))
        
        trending_count = 0
        
        for row in result:
            skill_id, name, recent, prev = row
            
            if prev > 0:
                growth = ((recent - prev) / prev) * 100
            elif recent > 0:
                growth = 100
            else:
                growth = 0
            
            # Update trending score
            trending_score = min(100, max(0, 50 + growth))
            
            db.execute(text("""
                UPDATE skills 
                SET trending_score = :trending,
                    updated_at = NOW()
                WHERE id = :skill_id
            """), {'trending': trending_score, 'skill_id': skill_id})
            
            if growth > 20:
                trending_count += 1
        
        db.commit()
        print(f"Found {trending_count} trending skills")
        return trending_count
        
    finally:
        db.close()

def generate_market_report(**context):
    """Generate market intelligence summary"""
    from sqlalchemy import text
    import json
    import uuid
    
    db = get_db_session()
    
    try:
        # Top demanded skills
        top_skills = db.execute(text("""
            SELECT name, popularity_score FROM skills
            ORDER BY popularity_score DESC LIMIT 10
        """)).fetchall()
        
        # Trending skills
        trending = db.execute(text("""
            SELECT name, trending_score FROM skills
            WHERE trending_score > 60
            ORDER BY trending_score DESC LIMIT 10
        """)).fetchall()
        
        # Job stats
        job_stats = db.execute(text("""
            SELECT 
                COUNT(*) as total_jobs,
                COUNT(CASE WHEN location_type = 'remote' THEN 1 END) as remote_jobs,
                AVG(salary_max) as avg_salary
            FROM jobs WHERE is_active = TRUE
        """)).fetchone()
        
        report = {
            'generated_at': datetime.now().isoformat(),
            'top_skills': [{'name': s[0], 'score': s[1]} for s in top_skills],
            'trending_skills': [{'name': s[0], 'score': s[1]} for s in trending],
            'job_market': {
                'total_active_jobs': job_stats[0],
                'remote_jobs': job_stats[1],
                'avg_salary': float(job_stats[2]) if job_stats[2] else 0
            }
        }
        
        # Save report
        db.execute(text("""
            INSERT INTO market_intelligence (id, report_type, report_data, generated_at, created_at)
            VALUES (:id, 'weekly_summary', :data, NOW(), NOW())
            ON DUPLICATE KEY UPDATE report_data = :data, generated_at = NOW()
        """), {'id': str(uuid.uuid4()), 'data': json.dumps(report)})
        
        db.commit()
        print(f"Market report generated")
        return report
        
    except Exception as e:
        print(f"Error generating report (table may not exist): {str(e)}")
        return {}
    finally:
        db.close()

with DAG(
    'market_intelligence_pipeline',
    default_args=default_args,
    description='Analyze job market trends',
    schedule_interval='0 0 * * *',  # Daily at midnight
    start_date=days_ago(1),
    catchup=False,
    tags=['market', 'analytics', 'trends'],
) as dag:

    demand_task = PythonOperator(
        task_id='analyze_skill_demand',
        python_callable=analyze_skill_demand,
    )

    trending_task = PythonOperator(
        task_id='identify_trending_skills',
        python_callable=identify_trending_skills,
    )

    report_task = PythonOperator(
        task_id='generate_market_report',
        python_callable=generate_market_report,
    )

    demand_task >> trending_task >> report_task

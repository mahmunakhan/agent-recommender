"""
DAG 7: Learning Path Generation Pipeline
Generates personalized learning paths based on skill gaps.
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

def generate_learning_paths(**context):
    """Generate learning paths for users with skill gaps"""
    from sqlalchemy import text
    
    db = get_db_session()
    paths_created = 0
    
    try:
        # Get users with skill gaps
        users_result = db.execute(text("""
            SELECT DISTINCT user_id FROM skill_gaps WHERE is_addressed = FALSE
        """))
        
        users = [row[0] for row in users_result]
        print(f"Generating learning paths for {len(users)} users")
        
        for user_id in users:
            # Get skill gaps
            gaps_result = db.execute(text("""
                SELECT sg.id, sg.skill_id, sg.priority_score, s.name
                FROM skill_gaps sg
                JOIN skills s ON sg.skill_id = s.id
                WHERE sg.user_id = :user_id
                AND sg.is_addressed = FALSE
                ORDER BY sg.priority_score DESC
                LIMIT 5
            """), {'user_id': user_id})
            
            gaps = list(gaps_result)
            
            # Clear old learning paths
            db.execute(text("""
                DELETE FROM user_learning_paths 
                WHERE user_id = :user_id AND status = 'recommended'
            """), {'user_id': user_id})
            
            sequence = 1
            
            for gap in gaps:
                gap_id, skill_id, priority, skill_name = gap
                
                # Find learning resources for this skill
                resources_result = db.execute(text("""
                    SELECT id, title, resource_type, difficulty_level
                    FROM learning_resources
                    WHERE skill_id = :skill_id
                    AND is_active = TRUE
                    ORDER BY quality_score DESC
                    LIMIT 3
                """), {'skill_id': skill_id})
                
                resources = list(resources_result)
                
                for resource in resources:
                    resource_id, title, res_type, difficulty = resource
                    
                    priority_label = 'critical' if priority > 70 else 'high' if priority > 40 else 'medium'
                    
                    db.execute(text("""
                        INSERT INTO user_learning_paths
                        (id, user_id, skill_gap_id, resource_id, sequence_order, priority, status, 
                         recommended_reason, created_at)
                        VALUES
                        (:id, :user_id, :gap_id, :resource_id, :sequence, :priority, 'recommended',
                         :reason, NOW())
                    """), {
                        'id': str(uuid.uuid4()),
                        'user_id': user_id,
                        'gap_id': gap_id,
                        'resource_id': resource_id,
                        'sequence': sequence,
                        'priority': priority_label,
                        'reason': f'Recommended to improve your {skill_name} skills'
                    })
                    
                    sequence += 1
                    paths_created += 1
            
            db.commit()
        
        print(f"Created {paths_created} learning path items")
        return paths_created
        
    finally:
        db.close()

with DAG(
    'learning_path_generation_pipeline',
    default_args=default_args,
    description='Generate personalized learning paths',
    schedule_interval='0 */6 * * *',
    start_date=days_ago(1),
    catchup=False,
    tags=['learning', 'skills', 'recommendations'],
) as dag:

    generate_task = PythonOperator(
        task_id='generate_learning_paths',
        python_callable=generate_learning_paths,
    )

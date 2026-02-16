"""
DAG 10: System Health Check Pipeline
Monitors system health and sends alerts.
Runs every hour.
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
    'retries': 1,
    'retry_delay': timedelta(minutes=2),
}

def get_db_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    db_url = os.getenv('APP_DATABASE_URL')
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    return Session()

def check_database_health(**context):
    """Check database connectivity and basic stats"""
    from sqlalchemy import text
    
    db = get_db_session()
    health = {'status': 'healthy', 'checks': []}
    
    try:
        # Check connection
        db.execute(text("SELECT 1"))
        health['checks'].append({'name': 'db_connection', 'status': 'ok'})
        
        # Check table counts
        tables = {
            'users': 'SELECT COUNT(*) FROM users',
            'jobs': 'SELECT COUNT(*) FROM jobs WHERE is_active = TRUE',
            'profiles': 'SELECT COUNT(*) FROM profiles WHERE is_verified = TRUE',
            'applications': 'SELECT COUNT(*) FROM applications',
        }
        
        for table, query in tables.items():
            result = db.execute(text(query)).fetchone()
            health['checks'].append({
                'name': f'{table}_count',
                'value': result[0],
                'status': 'ok'
            })
        
        print(f"Database health: {health}")
        context['task_instance'].xcom_push(key='db_health', value=health)
        return health
        
    except Exception as e:
        health['status'] = 'unhealthy'
        health['error'] = str(e)
        return health
    finally:
        db.close()

def check_milvus_health(**context):
    """Check Milvus vector database health"""
    health = {'status': 'healthy', 'checks': []}
    
    try:
        from pymilvus import connections, utility
        
        connections.connect(
            alias="default",
            host=os.getenv('MILVUS_HOST', 'localhost'),
            port=os.getenv('MILVUS_PORT', '19530')
        )
        
        health['checks'].append({'name': 'milvus_connection', 'status': 'ok'})
        
        # Check collections
        collections = utility.list_collections()
        health['checks'].append({
            'name': 'collections',
            'value': len(collections),
            'status': 'ok'
        })
        
        connections.disconnect("default")
        print(f"Milvus health: {health}")
        context['task_instance'].xcom_push(key='milvus_health', value=health)
        return health
        
    except Exception as e:
        health['status'] = 'unhealthy'
        health['error'] = str(e)
        return health

def check_minio_health(**context):
    """Check MinIO storage health"""
    health = {'status': 'healthy', 'checks': []}
    
    try:
        from minio import Minio
        
        client = Minio(
            os.getenv('MINIO_ENDPOINT', 'localhost:9000'),
            access_key=os.getenv('MINIO_ACCESS_KEY', 'minioadmin'),
            secret_key=os.getenv('MINIO_SECRET_KEY', 'minioadmin123'),
            secure=False
        )
        
        # Check bucket exists
        buckets = client.list_buckets()
        health['checks'].append({
            'name': 'buckets',
            'value': len(buckets),
            'status': 'ok'
        })
        
        print(f"MinIO health: {health}")
        context['task_instance'].xcom_push(key='minio_health', value=health)
        return health
        
    except Exception as e:
        health['status'] = 'unhealthy'
        health['error'] = str(e)
        return health

def generate_health_report(**context):
    """Generate overall health report"""
    from sqlalchemy import text
    import json
    
    db_health = context['task_instance'].xcom_pull(key='db_health', task_ids='check_database_health')
    milvus_health = context['task_instance'].xcom_pull(key='milvus_health', task_ids='check_milvus_health')
    minio_health = context['task_instance'].xcom_pull(key='minio_health', task_ids='check_minio_health')
    
    overall_status = 'healthy'
    if any(h.get('status') == 'unhealthy' for h in [db_health, milvus_health, minio_health] if h):
        overall_status = 'unhealthy'
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'overall_status': overall_status,
        'components': {
            'database': db_health,
            'milvus': milvus_health,
            'minio': minio_health
        }
    }
    
    print(f"Overall system status: {overall_status}")
    
    # Send alert notification if unhealthy
    if overall_status == 'unhealthy':
        db = get_db_session()
        try:
            # Get admin users
            admins = db.execute(text("SELECT id FROM users WHERE role = 'admin'")).fetchall()
            
            for admin in admins:
                db.execute(text("""
                    INSERT INTO notifications
                    (id, user_id, notification_type, title, message, priority, channels, created_at)
                    VALUES
                    (:id, :user_id, 'system_alert', 'System Health Alert', 
                     'One or more system components are unhealthy. Please check immediately.',
                     'high', '["in_app", "email"]', NOW())
                """), {'id': str(uuid.uuid4()), 'user_id': admin[0]})
            
            db.commit()
            print("Alert notifications sent to admins")
        finally:
            db.close()
    
    return report

with DAG(
    'system_health_check_pipeline',
    default_args=default_args,
    description='Monitor system health',
    schedule_interval='0 * * * *',  # Every hour
    start_date=days_ago(1),
    catchup=False,
    tags=['health', 'monitoring', 'alerts'],
) as dag:

    db_check = PythonOperator(
        task_id='check_database_health',
        python_callable=check_database_health,
    )

    milvus_check = PythonOperator(
        task_id='check_milvus_health',
        python_callable=check_milvus_health,
    )

    minio_check = PythonOperator(
        task_id='check_minio_health',
        python_callable=check_minio_health,
    )

    report_task = PythonOperator(
        task_id='generate_health_report',
        python_callable=generate_health_report,
    )

    [db_check, milvus_check, minio_check] >> report_task

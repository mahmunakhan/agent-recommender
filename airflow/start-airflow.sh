#!/bin/bash
# Airflow Startup Script

echo "Starting Apache Airflow..."

# Set environment variables
export AIRFLOW_HOME=/opt/airflow
export GROQ_API_KEY=${GROQ_API_KEY:-your_groq_api_key}

# Initialize database (first time only)
airflow db migrate

# Create admin user (first time only)
airflow users create \
    --username admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@jobmatch.ai \
    --password admin123 2>/dev/null || true

echo "Airflow initialized!"
echo "Starting webserver and scheduler..."

# Start scheduler in background
airflow scheduler &

# Start webserver
airflow webserver --port 8080
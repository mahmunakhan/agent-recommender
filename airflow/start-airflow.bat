@echo off
echo Starting Apache Airflow with Docker Compose...
cd %~dp0..
docker-compose -f docker-compose.airflow.yml up -d
echo.
echo Airflow is starting...
echo Web UI will be available at: http://localhost:8080
echo Username: admin
echo Password: admin123
echo.
echo Waiting for Airflow to initialize (30 seconds)...
timeout /t 30
start http://localhost:8080

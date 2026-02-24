"""
AI Job Recommendation Engine - FastAPI Application
"""


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import services
from app.services import database, milvus_service, minio_service, embedding_service

# Import routers
from app.routers.auth import router as auth_router
from app.routers.skills import router as skills_router
from app.routers.jobs import router as jobs_router
from app.routers.profiles import router as profiles_router
from app.routers.recommendations import router as recommendations_router
from app.routers.applications import router as applications_router
from app.routers.notifications import router as notifications_router
from app.routers.scheduled_tasks import router as scheduled_tasks_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    logger.info("Starting AI Job Recommendation Engine...")
    logger.info("Connecting to services...")

    # Test database
    if database.test_connection():
        logger.info("MySQL connected")
    else:
        logger.error("MySQL connection failed")

    # Initialize Milvus
    try:
        milvus_service.connect()
        logger.info("Milvus connected")
    except Exception as e:
        logger.warning(f"Milvus: {e}")

    # Initialize MinIO
    try:
        minio_service.connect()
        minio_service.create_bucket()
        exists = minio_service.client.bucket_exists("resumes")
        logger.info(f"MinIO connected, bucket exists: {exists}")
    except Exception as e:
        logger.warning(f"MinIO: {e}")

    # Embedding model loads on first use
    logger.info("Embedding model will load on first use")

    # Check Groq API key
    from app.config import settings
    if settings.GROQ_API_KEY and settings.GROQ_API_KEY != "your-groq-api-key":
        logger.info("Groq API key configured")
    else:
        logger.warning("Groq API key not configured")

    logger.info("Application startup complete!")

    yield

    # Shutdown
    logger.info("Shutting down...")
    try:
        milvus_service.close()
    except:
        pass


# Create app
app = FastAPI(
    title="AI Job Recommendation Engine",
    description="AI-powered job recommendation engine with skill gap analysis",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== REGISTER ROUTERS =====
app.include_router(auth_router)
app.include_router(skills_router)
app.include_router(jobs_router)
app.include_router(profiles_router)
app.include_router(recommendations_router)
app.include_router(applications_router)
app.include_router(notifications_router)
app.include_router(scheduled_tasks_router)


# ===== HEALTH ENDPOINTS =====
@app.get("/", tags=["Health"])
async def root():
    return {"service": "AI Job Recommendation Engine", "version": "1.0.0", "status": "running"}


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}


@app.get("/health/detailed", tags=["Health"])
async def health_detailed():
    health = {"database": False, "milvus": False, "minio": False, "embedding": False}

    try:
        health["database"] = database.test_connection()
    except:
        pass

    try:
        from pymilvus import connections
        connections.connect(alias="health", host="localhost", port="19530")
        health["milvus"] = True
        connections.disconnect("health")
    except:
        pass

    try:
        health["minio"] = minio_service.client.bucket_exists("resumes")
    except:
        pass

    try:
        emb = embedding_service.generate_embedding("test")
        health["embedding"] = emb is not None
    except:
        pass

    return {"status": "healthy" if all(health.values()) else "degraded", "services": health}


@app.get("/stats", tags=["Health"])
async def stats():
    """Get database and service statistics"""
    result = {"database": {}, "vectors": {}, "storage": {}}

    try:
        result["database"] = database.get_table_counts()
    except Exception as e:
        result["database"] = {"error": str(e)}

    try:
        from pymilvus import Collection, connections
        connections.connect(alias="stats", host="localhost", port="19530")

        for name in ["profile_embeddings", "job_embeddings"]:
            try:
                col = Collection(name, using="stats")
                result["vectors"][name] = {"exists": True, "num_entities": col.num_entities}
            except:
                result["vectors"][name] = {"exists": False}

        connections.disconnect("stats")
    except Exception as e:
        result["vectors"] = {"error": str(e)}

    try:
        bucket = "resumes"
        exists = minio_service.client.bucket_exists(bucket)
        count = 0
        if exists:
            objects = minio_service.client.list_objects(bucket)
            count = sum(1 for _ in objects)
        result["storage"] = {"bucket": bucket, "exists": exists, "file_count": count}
    except Exception as e:
        result["storage"] = {"error": str(e)}

    return result


# ===== TEST ENDPOINTS =====
@app.get("/test/embedding", tags=["Test"])
async def test_embedding():
    try:
        text = "Senior Python developer with machine learning experience"
        embedding = embedding_service.generate_embedding(text)
        return {"status": "success", "text": text, "embedding_dim": len(embedding), "sample": embedding[:5]}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/test/llm", tags=["Test"])
async def test_llm():
    try:
        from app.services import llm_service
        result = llm_service.test_connection()
        return {"status": "success", "response": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}



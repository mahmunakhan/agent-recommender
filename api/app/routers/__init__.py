"""
API Routers
"""

from app.routers.auth import router as auth_router
from app.routers.skills import router as skills_router
from app.routers.jobs import router as jobs_router
from app.routers.profiles import router as profiles_router
from app.routers.recommendations import router as recommendations_router

__all__ = [
    "auth_router",
    "skills_router", 
    "jobs_router",
    "profiles_router",
    "recommendations_router"
]
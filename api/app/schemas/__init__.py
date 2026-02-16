"""
Schemas Package
Export all Pydantic schemas
"""

from app.schemas.user import (
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
    SkillInput,
    ExperienceInput,
    EducationInput,
    ProfileCreate,
    ProfileResponse,
    ProfileWithSkills,
    Token,
    TokenData
)

from app.schemas.job import (
    JobSkillInput,
    JobCreate,
    JobResponse,
    JobDetail,
    JobSearch,
    RecommendationResponse,
    RecommendationFeedback,
    SkillGapResponse,
    LearningResourceResponse,
    LearningPathItemResponse,
    LearningPathResponse
)

__all__ = [
    # User
    "UserCreate",
    "UserLogin", 
    "UserResponse",
    "UserUpdate",
    "SkillInput",
    "ExperienceInput",
    "EducationInput",
    "ProfileCreate",
    "ProfileResponse",
    "ProfileWithSkills",
    "Token",
    "TokenData",
    
    # Job
    "JobSkillInput",
    "JobCreate",
    "JobResponse",
    "JobDetail",
    "JobSearch",
    "RecommendationResponse",
    "RecommendationFeedback",
    "SkillGapResponse",
    "LearningResourceResponse",
    "LearningPathItemResponse",
    "LearningPathResponse",
]
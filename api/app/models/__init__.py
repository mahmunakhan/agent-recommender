"""
Models Package
Export all SQLAlchemy models
"""

from app.models.user import User, Profile, generate_uuid
from app.models.skill import SkillCategory, Skill, SkillAlias, ProfileSkill
from app.models.job import JobSource, Job, JobSkill, Application, RecruiterAction
from app.models.recommendation import (
    Recommendation, 
    SkillGap, 
    LearningProvider, 
    LearningResource, 
    UserLearningPath
)
from app.models.system import AuditLog, Notification, MarketIntelligence, TrendingSkill

__all__ = [
    # User
    "User",
    "Profile",
    "generate_uuid",
    
    # Skills
    "SkillCategory",
    "Skill",
    "SkillAlias",
    "ProfileSkill",
    
    # Jobs
    "JobSource",
    "Job",
    "JobSkill",
    "Application",
    "RecruiterAction",
    
    # Recommendations
    "Recommendation",
    "SkillGap",
    "LearningProvider",
    "LearningResource",
    "UserLearningPath",
    
    # System
    "AuditLog",
    "Notification",
    "MarketIntelligence",
    "TrendingSkill",
]

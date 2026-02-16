"""
Job and Recommendation Schemas for API validation
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ============== Job Schemas ==============

class JobSkillInput(BaseModel):
    """Schema for job skill requirement"""
    skill_name: str
    importance: str = "high"  # critical, high, medium
    min_years: Optional[int] = None


class JobCreate(BaseModel):
    """Schema for creating a job"""
    title: str
    company_name: str
    description_raw: str
    location_city: Optional[str] = None
    location_country: Optional[str] = None
    location_type: str = "onsite"  # onsite, remote, hybrid
    employment_type: str = "full_time"  # full_time, part_time, contract, internship
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: str = "USD"
    experience_min_years: Optional[int] = None
    experience_max_years: Optional[int] = None
    required_skills: List[JobSkillInput] = []
    preferred_skills: List[str] = []


class JobResponse(BaseModel):
    """Schema for job response"""
    id: str
    title: str
    company_name: str
    company_logo_url: Optional[str]
    location_city: Optional[str]
    location_country: Optional[str]
    location_type: str
    employment_type: str
    salary_min: Optional[int]
    salary_max: Optional[int]
    salary_currency: Optional[str]
    experience_min_years: Optional[int]
    experience_max_years: Optional[int]
    is_active: bool
    posted_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class JobDetail(JobResponse):
    """Full job details"""
    description_raw: str
    description_clean: Optional[str]
    requirements_json: Optional[dict]
    skills: List[dict] = []


class JobSearch(BaseModel):
    """Schema for job search parameters"""
    query: Optional[str] = None
    location: Optional[str] = None
    location_type: Optional[str] = None
    employment_type: Optional[str] = None
    salary_min: Optional[int] = None
    experience_max: Optional[int] = None
    skills: List[str] = []
    page: int = 1
    page_size: int = 20


# ============== Recommendation Schemas ==============

class RecommendationResponse(BaseModel):
    """Schema for job recommendation"""
    id: int
    job_id: str
    match_score: float
    skill_match_score: float
    experience_match_score: float
    location_match_score: float
    semantic_similarity: float
    ranking_position: int
    matched_skills: List[str]
    missing_skills: List[str]
    recommendation_reason: Optional[str]
    is_viewed: bool
    created_at: datetime
    
    # Include job details
    job: Optional[JobResponse] = None
    
    class Config:
        from_attributes = True


class RecommendationFeedback(BaseModel):
    """Schema for user feedback on recommendation"""
    feedback: str  # interested, not_interested, applied, saved


# ============== Skill Gap Schemas ==============

class SkillGapResponse(BaseModel):
    """Schema for skill gap"""
    id: str
    skill_id: str
    skill_name: str
    gap_type: str  # missing, insufficient, outdated
    current_level: Optional[str]
    target_level: str
    priority_score: float
    frequency_in_jobs: int
    analysis_text: Optional[str]
    is_addressed: bool
    
    class Config:
        from_attributes = True


# ============== Learning Path Schemas ==============

class LearningResourceResponse(BaseModel):
    """Schema for learning resource"""
    id: str
    title: str
    url: str
    provider_name: str
    resource_type: str
    difficulty_level: str
    duration_hours: Optional[float]
    price: Optional[float]
    is_free: bool
    rating: Optional[float]
    
    class Config:
        from_attributes = True


class LearningPathItemResponse(BaseModel):
    """Schema for learning path item"""
    id: str
    sequence_order: int
    priority: str
    status: str
    recommended_reason: Optional[str]
    resource: LearningResourceResponse
    
    class Config:
        from_attributes = True


class LearningPathResponse(BaseModel):
    """Schema for complete learning path"""
    user_id: str
    skill_gaps_count: int
    items: List[LearningPathItemResponse]
    total_hours: float
    total_cost: float
"""
User and Profile Schemas for API validation
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime


# ============== User Schemas ==============

class UserCreate(BaseModel):
    """Schema for creating a new user"""
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: str = "candidate"


class UserLogin(BaseModel):
    """Schema for user login"""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Schema for user response"""
    id: str
    email: str
    role: str
    first_name: Optional[str]
    last_name: Optional[str]
    is_active: bool
    email_verified: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Schema for updating user"""
    first_name: Optional[str] = None
    last_name: Optional[str] = None


# ============== Profile Schemas ==============

class SkillInput(BaseModel):
    """Schema for skill input"""
    name: str
    proficiency: str = "intermediate"  # beginner, intermediate, advanced, expert
    years: Optional[int] = None


class ExperienceInput(BaseModel):
    """Schema for experience input"""
    company: str
    title: str
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None
    skills_used: List[str] = []


class EducationInput(BaseModel):
    """Schema for education input"""
    institution: str
    degree: str
    field: Optional[str] = None
    year: Optional[int] = None


class ProfileCreate(BaseModel):
    """Schema for creating/updating profile"""
    headline: Optional[str] = None
    summary: Optional[str] = None
    location_city: Optional[str] = None
    location_country: Optional[str] = None
    years_experience: Optional[int] = None
    desired_role: Optional[str] = None
    desired_salary_min: Optional[int] = None
    desired_salary_max: Optional[int] = None
    salary_currency: str = "USD"
    is_open_to_work: bool = True
    skills: List[SkillInput] = []
    experience: List[ExperienceInput] = []
    education: List[EducationInput] = []


class ProfileResponse(BaseModel):
    """Schema for profile response"""
    id: str
    user_id: str
    headline: Optional[str]
    summary: Optional[str]
    location_city: Optional[str]
    location_country: Optional[str]
    years_experience: Optional[int]
    desired_role: Optional[str]
    desired_salary_min: Optional[int]
    desired_salary_max: Optional[int]
    salary_currency: Optional[str]
    is_open_to_work: bool
    is_verified: bool
    verification_score: Optional[float]
    resume_s3_path: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ProfileWithSkills(ProfileResponse):
    """Profile with skills included"""
    skills: List[dict] = []
    parsed_json_draft: Optional[dict] = None
    validated_json: Optional[dict] = None


# ============== Auth Schemas ==============

class Token(BaseModel):
    """JWT token response"""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Data encoded in JWT"""
    user_id: str
    email: str
    role: str
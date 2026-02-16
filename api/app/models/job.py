"""
Job and Application Models
"""

from sqlalchemy import Column, String, Boolean, DateTime, Integer, Float, Text, ForeignKey, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.mysql import CHAR, JSON

from app.services.database import Base
from app.models.user import generate_uuid


class JobSource(Base):
    """Job data sources registry"""
    __tablename__ = "job_sources"

    id = Column(CHAR(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), unique=True, nullable=False)
    source_type = Column(String(20), nullable=False)  # scraper, api, manual, rss
    base_url = Column(String(500))
    config_json = Column(JSON)
    is_active = Column(Boolean, default=True, nullable=False)
    last_sync_at = Column(DateTime(timezone=True))
    sync_frequency_hours = Column(Integer, default=24, nullable=False)
    jobs_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    jobs = relationship("Job", back_populates="source")


class Job(Base):
    """Job postings"""
    __tablename__ = "jobs"

    id = Column(CHAR(36), primary_key=True, default=generate_uuid)
    source_id = Column(CHAR(36), ForeignKey("job_sources.id"))
    external_id = Column(String(255))
    source_type = Column(String(20), nullable=False)  # internal, scrape, upload, api
    
    # Recruiter who posted the job (for internal jobs)
    posted_by_id = Column(CHAR(36), ForeignKey("users.id"), nullable=True)
    
    title = Column(String(255), nullable=False)
    company_name = Column(String(255), nullable=False)
    company_logo_url = Column(String(500))
    description_raw = Column(Text, nullable=False)
    description_clean = Column(Text)
    requirements_json = Column(JSON)
    location_city = Column(String(100))
    location_country = Column(String(100))
    location_type = Column(String(20), default="onsite", nullable=False)  # onsite, remote, hybrid
    employment_type = Column(String(20), default="full_time", nullable=False)  # full_time, part_time, contract, internship
    salary_min = Column(Integer)
    salary_max = Column(Integer)
    salary_currency = Column(String(3), default="USD")
    experience_min_years = Column(Integer)
    experience_max_years = Column(Integer)
    is_active = Column(Boolean, default=True, nullable=False)
    posted_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True))
    last_vectorized_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    source = relationship("JobSource", back_populates="jobs")
    posted_by = relationship("User", back_populates="posted_jobs", foreign_keys=[posted_by_id])
    skills = relationship("JobSkill", back_populates="job", cascade="all, delete-orphan")
    applications = relationship("Application", back_populates="job", cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="job", cascade="all, delete-orphan")


class JobSkill(Base):
    """Junction: jobs to skills"""
    __tablename__ = "job_skills"

    id = Column(CHAR(36), primary_key=True, default=generate_uuid)
    job_id = Column(CHAR(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    skill_id = Column(CHAR(36), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    requirement_type = Column(String(20), nullable=False)  # required, preferred, nice_to_have
    min_years = Column(Integer)
    min_proficiency = Column(String(20))  # beginner, intermediate, advanced, expert
    weight = Column(Float, default=1.0, nullable=False)
    extracted_text = Column(String(255))
    confidence_score = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    job = relationship("Job", back_populates="skills")
    skill = relationship("Skill", back_populates="job_skills")


class Application(Base):
    """Job applications"""
    __tablename__ = "applications"

    id = Column(CHAR(36), primary_key=True, default=generate_uuid)
    user_id = Column(CHAR(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(CHAR(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    recommendation_id = Column(BigInteger, ForeignKey("recommendations.id"))
    status = Column(String(30), default="applied", nullable=False)
    cover_letter = Column(Text)
    custom_resume_path = Column(String(500))
    source = Column(String(20), nullable=False)  # recommendation, search, direct, referral
    match_score_at_apply = Column(Float)
    recruiter_notes = Column(Text)
    rejection_reason = Column(String(100))
    applied_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    status_updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="applications")
    job = relationship("Job", back_populates="applications")
    recommendation = relationship("Recommendation", back_populates="application")
    recruiter_actions = relationship("RecruiterAction", back_populates="application", cascade="all, delete-orphan")


class RecruiterAction(Base):
    """Recruiter activity log"""
    __tablename__ = "recruiter_actions"

    id = Column(CHAR(36), primary_key=True, default=generate_uuid)
    application_id = Column(CHAR(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    recruiter_id = Column(CHAR(36), ForeignKey("users.id"), nullable=False)
    action_type = Column(String(30), nullable=False)
    previous_status = Column(String(30))
    new_status = Column(String(30))
    action_details = Column(JSON)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    application = relationship("Application", back_populates="recruiter_actions")
    recruiter = relationship("User")
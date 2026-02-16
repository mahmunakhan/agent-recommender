"""
Recommendation and Learning Models
"""

from sqlalchemy import Column, String, Boolean, DateTime, Integer, Float, Text, ForeignKey, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.mysql import CHAR, JSON

from app.services.database import Base
from app.models.user import generate_uuid


class Recommendation(Base):
    """Job recommendations"""
    __tablename__ = "recommendations"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(CHAR(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(CHAR(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    batch_id = Column(CHAR(36), nullable=False)
    match_score = Column(Float, nullable=False)
    skill_match_score = Column(Float, nullable=False)
    experience_match_score = Column(Float, nullable=False)
    location_match_score = Column(Float, nullable=False)
    semantic_similarity = Column(Float, nullable=False)
    ranking_position = Column(Integer, nullable=False)
    matched_skills = Column(JSON, nullable=False)
    missing_skills = Column(JSON, nullable=False)
    gap_analysis = Column(Text)
    recommendation_reason = Column(Text)
    user_feedback = Column(String(20))  # interested, not_interested, applied, saved
    feedback_at = Column(DateTime(timezone=True))
    is_viewed = Column(Boolean, default=False, nullable=False)
    viewed_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="recommendations")
    job = relationship("Job", back_populates="recommendations")
    application = relationship("Application", back_populates="recommendation", uselist=False)


class SkillGap(Base):
    """Identified skill gaps"""
    __tablename__ = "skill_gaps"
    
    id = Column(CHAR(36), primary_key=True, default=generate_uuid)
    user_id = Column(CHAR(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    skill_id = Column(CHAR(36), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    gap_type = Column(String(20), nullable=False)  # missing, insufficient, outdated
    current_level = Column(String(20))  # none, beginner, intermediate, advanced, expert
    target_level = Column(String(20), nullable=False)
    priority_score = Column(Float, nullable=False)
    frequency_in_jobs = Column(Integer, default=0, nullable=False)
    avg_salary_impact = Column(Float)
    source = Column(String(20), nullable=False)  # job_matching, market_analysis, manual
    analysis_text = Column(Text)
    is_addressed = Column(Boolean, default=False, nullable=False)
    addressed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="skill_gaps")
    skill = relationship("Skill")
    learning_paths = relationship("UserLearningPath", back_populates="skill_gap")


class LearningProvider(Base):
    """Learning content providers"""
    __tablename__ = "learning_providers"
    
    id = Column(CHAR(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), unique=True, nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    website_url = Column(String(500), nullable=False)
    logo_url = Column(String(500))
    provider_type = Column(String(20), nullable=False)  # mooc, video, documentation, certification, bootcamp
    quality_score = Column(Float, default=50, nullable=False)
    has_certificates = Column(Boolean, default=False, nullable=False)
    has_free_content = Column(Boolean, default=False, nullable=False)
    avg_course_price = Column(Float)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    resources = relationship("LearningResource", back_populates="provider")


class LearningResource(Base):
    """Learning resources catalog"""
    __tablename__ = "learning_resources"
    
    id = Column(CHAR(36), primary_key=True, default=generate_uuid)
    provider_id = Column(CHAR(36), ForeignKey("learning_providers.id"), nullable=False)
    skill_id = Column(CHAR(36), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    url = Column(String(500), nullable=False)
    description = Column(Text)
    resource_type = Column(String(20), nullable=False)  # course, tutorial, video, book, certification, article
    difficulty_level = Column(String(20), nullable=False)  # beginner, intermediate, advanced, expert
    duration_hours = Column(Float)
    price = Column(Float)
    is_free = Column(Boolean, default=False, nullable=False)
    rating = Column(Float)
    reviews_count = Column(Integer)
    enrollment_count = Column(Integer)
    has_certificate = Column(Boolean, default=False, nullable=False)
    language = Column(String(10), default="en", nullable=False)
    quality_score = Column(Float, default=50, nullable=False)
    last_verified_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    provider = relationship("LearningProvider", back_populates="resources")
    skill = relationship("Skill", back_populates="learning_resources")
    learning_paths = relationship("UserLearningPath", back_populates="resource")


class UserLearningPath(Base):
    """Personalized learning paths"""
    __tablename__ = "user_learning_paths"
    
    id = Column(CHAR(36), primary_key=True, default=generate_uuid)
    user_id = Column(CHAR(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    skill_gap_id = Column(CHAR(36), ForeignKey("skill_gaps.id", ondelete="SET NULL"))
    resource_id = Column(CHAR(36), ForeignKey("learning_resources.id", ondelete="CASCADE"), nullable=False)
    sequence_order = Column(Integer, nullable=False)
    priority = Column(String(20), nullable=False)  # critical, high, medium, low
    status = Column(String(20), default="recommended", nullable=False)  # recommended, in_progress, completed, skipped
    recommended_reason = Column(Text)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    user_rating = Column(Integer)
    user_notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="learning_paths")
    skill_gap = relationship("SkillGap", back_populates="learning_paths")
    resource = relationship("LearningResource", back_populates="learning_paths")

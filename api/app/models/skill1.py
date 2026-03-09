"""
Skill and Taxonomy Models
"""

from sqlalchemy import Column, String, Boolean, DateTime, Integer, Float, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.mysql import CHAR, JSON

from app.services.database import Base
from app.models.user import generate_uuid


class SkillCategory(Base):
    """Hierarchical skill categories"""
    __tablename__ = "skill_categories"
    
    id = Column(CHAR(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    parent_id = Column(CHAR(36), ForeignKey("skill_categories.id"))
    description = Column(Text)
    icon = Column(String(50))
    display_order = Column(Integer, default=0, nullable=False)
    level = Column(Integer, default=0, nullable=False)
    path = Column(String(500), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    parent = relationship("SkillCategory", remote_side=[id], backref="children")
    skills = relationship("Skill", back_populates="category")


class Skill(Base):
    """Master skill taxonomy"""
    __tablename__ = "skills"
    
    id = Column(CHAR(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), unique=True, nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    category_id = Column(CHAR(36), ForeignKey("skill_categories.id"), nullable=False)
    description = Column(Text)
    skill_type = Column(String(20), nullable=False)  # technical, soft, domain, tool, language, certification
    is_verified = Column(Boolean, default=False, nullable=False)
    popularity_score = Column(Float, default=0, nullable=False)
    trending_score = Column(Float, default=0, nullable=False)
    external_ids = Column(JSON)
    extra_metadata = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    category = relationship("SkillCategory", back_populates="skills")
    aliases = relationship("SkillAlias", back_populates="skill", cascade="all, delete-orphan")
    profile_skills = relationship("ProfileSkill", back_populates="skill")
    job_skills = relationship("JobSkill", back_populates="skill")
    learning_resources = relationship("LearningResource", back_populates="skill")


class SkillAlias(Base):
    """Alternative names for skills"""
    __tablename__ = "skill_aliases"
    
    id = Column(CHAR(36), primary_key=True, default=generate_uuid)
    skill_id = Column(CHAR(36), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    alias = Column(String(100), nullable=False)
    alias_type = Column(String(20), nullable=False)  # abbreviation, alternate, misspelling, regional, version
    language = Column(String(10), default="en", nullable=False)
    is_preferred = Column(Boolean, default=False, nullable=False)
    source = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    skill = relationship("Skill", back_populates="aliases")


class ProfileSkill(Base):
    """Junction: profiles to skills"""
    __tablename__ = "profile_skills"
    
    id = Column(CHAR(36), primary_key=True, default=generate_uuid)
    profile_id = Column(CHAR(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    skill_id = Column(CHAR(36), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    proficiency_level = Column(String(20), nullable=False)  # beginner, intermediate, advanced, expert
    years_experience = Column(Float)
    is_primary = Column(Boolean, default=False, nullable=False)
    source = Column(String(20), nullable=False)  # parsed, manual, inferred
    confidence_score = Column(Float)
    last_used_date = Column(DateTime)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    profile = relationship("Profile", back_populates="skills")
    skill = relationship("Skill", back_populates="profile_skills")

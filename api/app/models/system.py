"""
System Models (Audit, Notifications)
"""

from sqlalchemy import Column, String, Boolean, DateTime, Integer, Float, Text, ForeignKey, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.mysql import CHAR, JSON

from app.services.database import Base
from app.models.user import generate_uuid


class AuditLog(Base):
    """System audit trail"""
    __tablename__ = "audit_log"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_type = Column(String(50), nullable=False)
    event_category = Column(String(20), nullable=False)  # user, job, recommendation, system, security, ai
    actor_id = Column(CHAR(36), ForeignKey("users.id", ondelete="SET NULL"))
    actor_type = Column(String(20), nullable=False)  # user, system, agent, api
    target_type = Column(String(50))
    target_id = Column(String(100))
    action = Column(String(20), nullable=False)  # create, read, update, delete, login, logout, error
    old_values = Column(JSON)
    new_values = Column(JSON)
    extra_metadata = Column(JSON)
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    actor = relationship("User")


class Notification(Base):
    """User notifications"""
    __tablename__ = "notifications"
    
    id = Column(CHAR(36), primary_key=True, default=generate_uuid)
    user_id = Column(CHAR(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    notification_type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    action_url = Column(String(500))
    extra_metadata = Column(JSON)
    priority = Column(String(10), default="normal", nullable=False)  # low, normal, high, urgent
    channels = Column(JSON, default=["in_app"], nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    read_at = Column(DateTime(timezone=True))
    is_sent = Column(Boolean, default=False, nullable=False)
    sent_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="notifications")


class MarketIntelligence(Base):
    """Market insights from AI agents"""
    __tablename__ = "market_intelligence"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    role_category = Column(String(100), nullable=False)
    location_scope = Column(String(100), default="global", nullable=False)
    analysis_type = Column(String(30), nullable=False)  # skill_demand, salary_trend, job_volume, emerging_roles
    data_json = Column(JSON, nullable=False)
    summary_text = Column(Text)
    confidence_score = Column(Float)
    sources = Column(JSON)
    agent_id = Column(String(100), nullable=False)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    valid_until = Column(DateTime(timezone=True), nullable=False)


class TrendingSkill(Base):
    """Time-series skill demand tracking"""
    __tablename__ = "trending_skills"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    skill_id = Column(CHAR(36), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_type = Column(String(10), nullable=False)  # daily, weekly, monthly
    job_posting_count = Column(Integer, default=0, nullable=False)
    avg_salary = Column(Float)
    demand_score = Column(Float, default=0, nullable=False)
    growth_rate = Column(Float)
    location_scope = Column(String(100), default="global", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    skill = relationship("Skill")


# Need to import Float for MarketIntelligence
from sqlalchemy import Float


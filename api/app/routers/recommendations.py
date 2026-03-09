"""
Recommendations Router
AI-powered job recommendations and skill gap analysis

Fixes applied:
- BUG FIX: Delete old recommendations before inserting new ones (duplicate key error)
- BUG FIX: regex -> pattern (FastAPI deprecation warning)
- PERFORMANCE: Batch load job skills instead of N+1 queries per job
- FEATURE: Added diversity bonus (different companies get slight boost)
- FEATURE: Added recommendation_reason text explaining why each job was recommended
- FEATURE: Added salary match info to response
- IMPROVEMENT: Better error handling with proper logging
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func, text, delete
from typing import List, Optional, Dict, Set
from datetime import datetime
import uuid
import logging

from app.services.database import get_db
from app.services import embedding_service, milvus_service, llm_service
from app.models import (
    User, Profile, ProfileSkill, Job, JobSkill, Skill,
    Recommendation, SkillGap, LearningResource, UserLearningPath
)
from app.utils import get_current_user
from app.schemas import TokenData

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


# ============================================
# Helper: Build skill name lookup cache
# ============================================
def _get_skill_names(skill_ids: List[str], db: Session) -> List[str]:
    """Batch fetch skill names by IDs."""
    if not skill_ids:
        return []
    skills = db.execute(
        select(Skill).where(Skill.id.in_(skill_ids))
    ).scalars().all()
    skill_map = {s.id: s.name for s in skills}
    return [skill_map[sid] for sid in skill_ids if sid in skill_map]


# ============================================
# Helper: Batch load all job skills for a list of jobs
# ============================================
def _batch_load_job_skills(job_ids: List[str], db: Session) -> Dict[str, List]:
    """Load all job_skills for multiple jobs in ONE query (fixes N+1 problem)."""
    if not job_ids:
        return {}
    
    all_job_skills = db.execute(
        select(JobSkill).where(JobSkill.job_id.in_(job_ids))
    ).scalars().all()
    
    result = {}
    for js in all_job_skills:
        if js.job_id not in result:
            result[js.job_id] = []
        result[js.job_id].append(js)
    
    return result


# ============================================
# Helper: Generate recommendation reason text
# ============================================
def _generate_reason(
    job_title: str, 
    matched_skill_names: List[str], 
    skill_score: float, 
    exp_score: float, 
    loc_score: float
) -> str:
    """Generate a human-readable recommendation reason."""
    parts = []
    
    if matched_skill_names:
        top_skills = matched_skill_names[:3]
        parts.append(f"Your skills in {', '.join(top_skills)} match this role")
    
    if exp_score >= 100:
        parts.append("your experience level is a strong fit")
    elif exp_score >= 70:
        parts.append("your experience is close to what's needed")
    
    if loc_score >= 100:
        parts.append("the location works for you")
    elif loc_score >= 70:
        parts.append("the job is in your country")
    
    if not parts:
        return f"This {job_title} role may align with your career goals"
    
    reason = parts[0]
    if len(parts) > 1:
        reason += ", " + ", and ".join(parts[1:])
    
    return reason + "."


# ============================================
# 1. GET /recommendations/jobs
# ============================================
@router.get("/jobs")
async def get_job_recommendations(
    limit: int = Query(20, ge=1, le=50),
    refresh: bool = Query(False, description="Force regenerate recommendations"),
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get personalized job recommendations for the current user.
    Uses hybrid approach: vector similarity + skill matching.
    
    Scoring weights (from spec):
    - skill_match: 40%
    - experience_match: 25%
    - location_match: 15%
    - semantic_similarity: 20%
    """
    # Get user profile
    profile = db.execute(
        select(Profile).where(Profile.user_id == current_user.user_id)
    ).scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found. Please create your profile first.")
    
    if not profile.is_verified:
        raise HTTPException(
            status_code=400, 
            detail="Profile must be verified to get recommendations. Please complete profile verification."
        )
    
    # Check for existing recent recommendations (cache for 24 hours)
    if not refresh:
        existing = db.execute(
            select(Recommendation)
            .where(Recommendation.user_id == current_user.user_id)
            .where(Recommendation.created_at > func.date_sub(func.now(), text("INTERVAL 1 DAY")))
            .order_by(Recommendation.ranking_position)
            .limit(limit)
        ).scalars().all()
        
        if existing:
            return _format_recommendations(existing, db)
    
    # ---- Generate new recommendations ----
    batch_id = str(uuid.uuid4())
    
    # Step 1: Get profile embedding and find similar jobs via Milvus
    similar_jobs = []
    candidate_job_ids = []
    
    try:
        profile_embedding = embedding_service.generate_profile_embedding({
            "headline": profile.headline,
            "summary": profile.summary,
            "validated_json": profile.validated_json
        })
        
        if profile_embedding:
            similar_jobs = milvus_service.search_similar_jobs(profile_embedding, top_k=100)
            candidate_job_ids = [r["job_id"] for r in similar_jobs]
    except Exception as e:
        logger.warning(f"Vector search unavailable, falling back to skill matching: {e}")
    
    # Step 2: Get user skills
    user_skills = db.execute(
        select(ProfileSkill, Skill)
        .join(Skill)
        .where(ProfileSkill.profile_id == profile.id)
    ).all()
    
    user_skill_ids = {ps.ProfileSkill.skill_id for ps in user_skills}
    user_skill_names = {ps.ProfileSkill.skill_id: ps.Skill.name for ps in user_skills}
    
    # Step 3: Get candidate jobs
    if candidate_job_ids:
        jobs = db.execute(
            select(Job).where(Job.id.in_(candidate_job_ids)).where(Job.is_active == True)
        ).scalars().all()
    else:
        # Fallback: get recent active jobs
        jobs = db.execute(
            select(Job)
            .where(Job.is_active == True)
            .order_by(Job.posted_at.desc())
            .limit(100)
        ).scalars().all()
    
    if not jobs:
        return {"recommendations": [], "count": 0, "message": "No active jobs found."}
    
    # Step 4: Batch load all job skills (ONE query instead of N queries)
    job_ids = [j.id for j in jobs]
    all_job_skills = _batch_load_job_skills(job_ids, db)
    
    # Build semantic similarity lookup from vector search results
    semantic_lookup = {}
    for r in similar_jobs:
        semantic_lookup[r.get("job_id")] = r.get("similarity", 0.5)
    
    # Step 5: Score and rank all jobs
    scored_jobs = []
    seen_companies = {}  # For diversity bonus
    
    for job in jobs:
        job_skills = all_job_skills.get(job.id, [])
        job_skill_ids = {js.skill_id for js in job_skills}
        required_skills = {js.skill_id for js in job_skills if js.requirement_type == "required"}
        
        # --- Skill Match Score (40%) ---
        if job_skill_ids:
            matched = user_skill_ids & job_skill_ids
            skill_match_score = (len(matched) / len(job_skill_ids)) * 100
        else:
            skill_match_score = 50  # Neutral if no skills defined
        
        # --- Experience Match Score (25%) ---
        exp_match_score = 100
        if job.experience_min_years and profile.years_experience:
            if profile.years_experience >= job.experience_min_years:
                exp_match_score = 100
            else:
                gap = job.experience_min_years - profile.years_experience
                exp_match_score = max(0, 100 - (gap * 20))
        
        # --- Location Match Score (15%) ---
        loc_match_score = 100
        if job.location_type == "remote":
            loc_match_score = 100
        elif profile.location_city and job.location_city:
            if profile.location_city.lower() == job.location_city.lower():
                loc_match_score = 100
            elif profile.location_country and job.location_country:
                if profile.location_country.lower() == job.location_country.lower():
                    loc_match_score = 70
                else:
                    loc_match_score = 30
        
        # --- Semantic Similarity (20%) ---
        semantic_sim = semantic_lookup.get(job.id, 0.5)
        
        # --- Overall Match Score ---
        match_score = (
            skill_match_score * 0.40 +
            exp_match_score * 0.25 +
            loc_match_score * 0.15 +
            (semantic_sim * 100) * 0.20
        )
        
        # --- Diversity Bonus (from spec: different companies get slight boost) ---
        company = (job.company_name or "").lower()
        if company not in seen_companies:
            seen_companies[company] = 0
            match_score += 2  # Small boost for first job from a company
        seen_companies[company] += 1
        
        # Cap at 100
        match_score = min(100, match_score)
        
        # Identify matched and missing skills
        matched_skills = list(user_skill_ids & job_skill_ids)
        missing_skills = list(required_skills - user_skill_ids)
        
        # Generate recommendation reason
        matched_names = [user_skill_names[sid] for sid in matched_skills if sid in user_skill_names]
        reason = _generate_reason(job.title, matched_names, skill_match_score, exp_match_score, loc_match_score)
        
        scored_jobs.append({
            "job": job,
            "match_score": match_score,
            "skill_match_score": skill_match_score,
            "experience_match_score": exp_match_score,
            "location_match_score": loc_match_score,
            "semantic_similarity": semantic_sim,
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "recommendation_reason": reason
        })
    
    # Sort by match score descending
    scored_jobs.sort(key=lambda x: x["match_score"], reverse=True)
    
    # Step 6: Delete old recommendations for this user (FIX for duplicate key error)
    try:
        db.execute(
            delete(Recommendation).where(Recommendation.user_id == current_user.user_id)
        )
    except Exception as e:
        logger.warning(f"Could not clear old recommendations: {e}")
        db.rollback()
    
    # Step 7: Save new recommendations
    recommendations = []
    for rank, scored in enumerate(scored_jobs[:limit], 1):
        rec = Recommendation(
            user_id=current_user.user_id,
            job_id=scored["job"].id,
            batch_id=batch_id,
            match_score=scored["match_score"],
            skill_match_score=scored["skill_match_score"],
            experience_match_score=scored["experience_match_score"],
            location_match_score=scored["location_match_score"],
            semantic_similarity=scored["semantic_similarity"],
            ranking_position=rank,
            matched_skills={"skill_ids": scored["matched_skills"]},
            missing_skills={"skill_ids": scored["missing_skills"]},
            recommendation_reason=scored["recommendation_reason"]
        )
        db.add(rec)
        recommendations.append(rec)
    
    try:
        db.commit()
    except Exception as e:
        logger.error(f"Failed to save recommendations: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to generate recommendations. Please try again.")
    
    return _format_recommendations(recommendations, db)


# ============================================
# Helper: Format recommendations for API response
# ============================================
def _format_recommendations(recommendations: List[Recommendation], db: Session) -> dict:
    """Format recommendations for response."""
    if not recommendations:
        return {"recommendations": [], "count": 0}
    
    # Batch collect all skill IDs we need to look up
    all_matched_ids = []
    all_missing_ids = []
    all_job_ids = []
    
    for rec in recommendations:
        all_job_ids.append(rec.job_id)
        if rec.matched_skills and rec.matched_skills.get("skill_ids"):
            all_matched_ids.extend(rec.matched_skills["skill_ids"][:5])
        if rec.missing_skills and rec.missing_skills.get("skill_ids"):
            all_missing_ids.extend(rec.missing_skills["skill_ids"][:5])
    
    # Batch load jobs
    jobs_data = db.execute(
        select(Job).where(Job.id.in_(all_job_ids))
    ).scalars().all()
    job_map = {j.id: j for j in jobs_data}
    
    # Batch load skill names
    all_skill_ids = list(set(all_matched_ids + all_missing_ids))
    skill_name_map = {}
    if all_skill_ids:
        skills = db.execute(
            select(Skill).where(Skill.id.in_(all_skill_ids))
        ).scalars().all()
        skill_name_map = {s.id: s.name for s in skills}
    
    # Build response
    results = []
    for rec in recommendations:
        job = job_map.get(rec.job_id)
        if not job:
            continue
        
        # Get skill names from cache
        matched_names = []
        missing_names = []
        
        if rec.matched_skills and rec.matched_skills.get("skill_ids"):
            matched_names = [
                skill_name_map[sid] 
                for sid in rec.matched_skills["skill_ids"][:5] 
                if sid in skill_name_map
            ]
        
        if rec.missing_skills and rec.missing_skills.get("skill_ids"):
            missing_names = [
                skill_name_map[sid] 
                for sid in rec.missing_skills["skill_ids"][:5] 
                if sid in skill_name_map
            ]
        
        results.append({
            "id": rec.id,
            "job": {
                "id": job.id,
                "title": job.title,
                "company_name": job.company_name,
                "location_city": job.location_city,
                "location_country": job.location_country,
                "location_type": job.location_type,
                "employment_type": job.employment_type,
                "salary_min": job.salary_min,
                "salary_max": job.salary_max,
                "salary_currency": job.salary_currency,
                "experience_min_years": job.experience_min_years,
                "posted_at": str(job.posted_at) if job.posted_at else None
            },
            "match_score": round(rec.match_score, 1),
            "skill_match_score": round(rec.skill_match_score, 1),
            "experience_match_score": round(rec.experience_match_score, 1),
            "location_match_score": round(rec.location_match_score, 1),
            "ranking_position": rec.ranking_position,
            "matched_skills": matched_names,
            "missing_skills": missing_names,
            "recommendation_reason": rec.recommendation_reason,
            "is_viewed": rec.is_viewed,
            "user_feedback": rec.user_feedback
        })
    
    return {"recommendations": results, "count": len(results)}


# ============================================
# 2. POST /recommendations/{id}/feedback
# ============================================
@router.post("/{recommendation_id}/feedback")
async def submit_feedback(
    recommendation_id: int,
    feedback: str = Query(..., pattern="^(interested|not_interested|applied|saved)$"),
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit feedback on a recommendation."""
    rec = db.execute(
        select(Recommendation)
        .where(Recommendation.id == recommendation_id)
        .where(Recommendation.user_id == current_user.user_id)
    ).scalar_one_or_none()
    
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    
    rec.user_feedback = feedback
    rec.feedback_at = datetime.utcnow()
    db.commit()
    
    return {"message": "Feedback recorded", "feedback": feedback}


# ============================================
# 3. POST /recommendations/{id}/view
# ============================================
@router.post("/{recommendation_id}/view")
async def mark_viewed(
    recommendation_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark a recommendation as viewed."""
    rec = db.execute(
        select(Recommendation)
        .where(Recommendation.id == recommendation_id)
        .where(Recommendation.user_id == current_user.user_id)
    ).scalar_one_or_none()
    
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    
    if not rec.is_viewed:
        rec.is_viewed = True
        rec.viewed_at = datetime.utcnow()
        db.commit()
    
    return {"message": "Marked as viewed"}


# ============================================
# 4. GET /recommendations/skill-gaps
# ============================================
@router.get("/skill-gaps")
async def get_skill_gaps(
    refresh: bool = Query(False, description="Force regenerate skill gaps"),
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get skill gap analysis based on target jobs."""
    
    # Return existing gaps unless refresh requested
    if not refresh:
        gaps = db.execute(
            select(SkillGap, Skill)
            .join(Skill)
            .where(SkillGap.user_id == current_user.user_id)
            .where(SkillGap.is_addressed == False)
            .order_by(SkillGap.priority_score.desc())
        ).all()
        
        if gaps:
            return {
                "skill_gaps": [
                    {
                        "id": g.SkillGap.id,
                        "skill_name": g.Skill.name,
                        "skill_type": g.Skill.skill_type,
                        "gap_type": g.SkillGap.gap_type,
                        "current_level": g.SkillGap.current_level,
                        "target_level": g.SkillGap.target_level,
                        "priority_score": round(g.SkillGap.priority_score, 1),
                        "frequency_in_jobs": g.SkillGap.frequency_in_jobs,
                        "analysis_text": g.SkillGap.analysis_text
                    }
                    for g in gaps
                ]
            }
    
    # Generate new gap analysis from recommendations
    recommendations = db.execute(
        select(Recommendation)
        .where(Recommendation.user_id == current_user.user_id)
        .order_by(Recommendation.match_score.desc())
        .limit(20)
    ).scalars().all()
    
    if not recommendations:
        return {"skill_gaps": [], "message": "No recommendations found. Get job recommendations first."}
    
    # Aggregate missing skills across all recommendations
    skill_frequency = {}
    for rec in recommendations:
        if rec.missing_skills and rec.missing_skills.get("skill_ids"):
            for skill_id in rec.missing_skills["skill_ids"]:
                skill_frequency[skill_id] = skill_frequency.get(skill_id, 0) + 1
    
    if not skill_frequency:
        return {"skill_gaps": [], "message": "No skill gaps detected. Your skills match well with available jobs!"}
    
    # Get user's current skills
    profile = db.execute(
        select(Profile).where(Profile.user_id == current_user.user_id)
    ).scalar_one_or_none()
    
    user_skill_levels = {}
    if profile:
        profile_skills = db.execute(
            select(ProfileSkill).where(ProfileSkill.profile_id == profile.id)
        ).scalars().all()
        user_skill_levels = {ps.skill_id: ps.proficiency_level for ps in profile_skills}
    
    # Clear old gaps for this user before inserting new ones
    db.execute(
        delete(SkillGap)
        .where(SkillGap.user_id == current_user.user_id)
        .where(SkillGap.source == "job_matching")
    )
    
    # Create skill gaps
    new_gaps = []
    for skill_id, frequency in sorted(skill_frequency.items(), key=lambda x: x[1], reverse=True)[:10]:
        skill = db.get(Skill, skill_id)
        if not skill:
            continue
        
        current_level = user_skill_levels.get(skill_id, "none")
        gap_type = "missing" if current_level == "none" else "insufficient"
        
        priority_score = min(100, frequency * 10 + (skill.popularity_score or 0) * 0.5)
        
        gap = SkillGap(
            user_id=current_user.user_id,
            skill_id=skill_id,
            gap_type=gap_type,
            current_level=current_level if current_level != "none" else None,
            target_level="intermediate",
            priority_score=priority_score,
            frequency_in_jobs=frequency,
            source="job_matching"
        )
        db.add(gap)
        new_gaps.append((gap, skill))
    
    try:
        db.commit()
    except Exception as e:
        logger.error(f"Failed to save skill gaps: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to generate skill gap analysis.")
    
    return {
        "skill_gaps": [
            {
                "id": g[0].id,
                "skill_name": g[1].name,
                "skill_type": g[1].skill_type,
                "gap_type": g[0].gap_type,
                "current_level": g[0].current_level,
                "target_level": g[0].target_level,
                "priority_score": round(g[0].priority_score, 1),
                "frequency_in_jobs": g[0].frequency_in_jobs
            }
            for g in new_gaps
        ]
    }


# ============================================
# 5. GET /recommendations/learning-path
# ============================================
@router.get("/learning-path")
async def get_learning_path(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get personalized learning path based on skill gaps."""
    gaps = db.execute(
        select(SkillGap)
        .where(SkillGap.user_id == current_user.user_id)
        .where(SkillGap.is_addressed == False)
        .order_by(SkillGap.priority_score.desc())
        .limit(5)
    ).scalars().all()
    
    if not gaps:
        return {"learning_path": [], "message": "No skill gaps found. Run skill gap analysis first."}
    
    # Batch load skills for all gaps
    gap_skill_ids = [g.skill_id for g in gaps]
    skills = db.execute(
        select(Skill).where(Skill.id.in_(gap_skill_ids))
    ).scalars().all()
    skill_map = {s.id: s for s in skills}
    
    # Find learning resources for each gap
    path_items = []
    sequence = 1
    
    for gap in gaps:
        skill = skill_map.get(gap.skill_id)
        
        resources = db.execute(
            select(LearningResource)
            .where(LearningResource.skill_id == gap.skill_id)
            .where(LearningResource.is_active == True)
            .order_by(LearningResource.quality_score.desc())
            .limit(3)
        ).scalars().all()
        
        for resource in resources:
            path_items.append({
                "sequence": sequence,
                "skill_name": skill.name if skill else "Unknown",
                "skill_gap_id": gap.id,
                "resource": {
                    "id": resource.id,
                    "title": resource.title,
                    "url": resource.url,
                    "resource_type": resource.resource_type,
                    "difficulty_level": resource.difficulty_level,
                    "duration_hours": resource.duration_hours,
                    "is_free": resource.is_free,
                    "rating": resource.rating
                },
                "priority": "critical" if gap.priority_score > 70 else "high" if gap.priority_score > 40 else "medium"
            })
            sequence += 1
    
    return {"learning_path": path_items, "total_items": len(path_items)}


# ============================================
# 6. GET /recommendations/ai-learning-path
# ============================================
@router.get("/ai-learning-path")
async def get_ai_learning_path(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get AI-powered personalized learning recommendations.
    Uses LLM agents to analyze skills and recommend learning topics.
    """
    from app.services.skill_agent_service import skill_agent
    
    # Get user profile
    profile = db.execute(
        select(Profile).where(Profile.user_id == current_user.user_id)
    ).scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Get current skills
    user_skills = db.execute(
        select(ProfileSkill, Skill)
        .join(Skill)
        .where(ProfileSkill.profile_id == profile.id)
    ).all()
    
    current_skills = [ps.Skill.name for ps in user_skills]
    
    if not current_skills:
        return {
            "message": "Add skills to your profile first",
            "ai_recommendations": []
        }
    
    # Get missing skills from skill gaps
    skill_gaps = db.execute(
        select(SkillGap, Skill)
        .join(Skill)
        .where(SkillGap.user_id == current_user.user_id)
        .where(SkillGap.is_addressed == False)
    ).all()
    
    missing_skills = [sg.Skill.name for sg in skill_gaps]
    
    # Get AI recommendations
    try:
        recommendations = skill_agent.get_complete_learning_recommendation(
            current_skills=current_skills,
            missing_skills=missing_skills,
            target_role=profile.desired_role
        )
        return recommendations
    except Exception as e:
        logger.error(f"AI learning path failed: {e}")
        # Fallback to basic recommendations if AI fails
        return {
            "message": "AI analysis completed with fallback",
            "current_skills": current_skills,
            "missing_skills": missing_skills,
            "ai_recommendations": [
                {
                    "skill": skill,
                    "learning_path": [
                        {
                            "order": 1,
                            "topic": f"{skill} Fundamentals",
                            "description": f"Learn the basics of {skill}",
                            "difficulty": "beginner",
                            "estimated_hours": 10,
                            "search_keywords": [skill.lower(), f"{skill.lower()} tutorial", f"learn {skill.lower()}"],
                            "platforms_to_check": ["Coursera", "Udemy", "YouTube", "freeCodeCamp"]
                        },
                        {
                            "order": 2,
                            "topic": f"{skill} Intermediate Concepts",
                            "description": f"Deepen your {skill} knowledge",
                            "difficulty": "intermediate",
                            "estimated_hours": 15,
                            "search_keywords": [f"{skill.lower()} advanced", f"{skill.lower()} projects"],
                            "platforms_to_check": ["Pluralsight", "LinkedIn Learning", "Udemy"]
                        },
                        {
                            "order": 3,
                            "topic": f"{skill} Real-World Projects",
                            "description": f"Apply {skill} in practical projects",
                            "difficulty": "intermediate",
                            "estimated_hours": 20,
                            "search_keywords": [f"{skill.lower()} project ideas", f"{skill.lower()} portfolio"],
                            "platforms_to_check": ["GitHub", "Dev.to", "Medium"]
                        }
                    ],
                    "projects": [f"Build a {skill} project", f"Contribute to open source {skill} projects"],
                    "certifications": []
                }
                for skill in (missing_skills or current_skills[:3])[:5]
            ],
            "error": str(e)
        }
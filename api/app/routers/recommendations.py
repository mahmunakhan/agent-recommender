"""
Recommendations Router
AI-powered job recommendations and skill gap analysis
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func, text
from typing import List, Optional
from datetime import datetime
import uuid

from app.services.database import get_db
from app.services import embedding_service, milvus_service, llm_service
from app.models import (
    User, Profile, ProfileSkill, Job, JobSkill, Skill,
    Recommendation, SkillGap, LearningResource, UserLearningPath
)
from app.utils import get_current_user
from app.schemas import TokenData

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.get("/jobs")
async def get_job_recommendations(
    limit: int = Query(20, ge=1, le=50),
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get personalized job recommendations for the current user.
    Uses hybrid approach: vector similarity + skill matching.
    """
    # Get user profile
    profile = db.execute(
        select(Profile).where(Profile.user_id == current_user.user_id)
    ).scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    if not profile.is_verified:
        raise HTTPException(
            status_code=400, 
            detail="Profile must be verified to get recommendations"
        )
    
    # Check for existing recent recommendations
    existing = db.execute(
        select(Recommendation)
        .where(Recommendation.user_id == current_user.user_id)
        .where(Recommendation.created_at > func.date_sub(func.now(), text("INTERVAL 1 DAY")))
        .order_by(Recommendation.ranking_position)
        .limit(limit)
    ).scalars().all()
    
    if existing:
        # Return cached recommendations
        return _format_recommendations(existing, db)
    
    # Generate new recommendations
    batch_id = str(uuid.uuid4())
    
    # Step 1: Get profile embedding and find similar jobs
    profile_embedding = embedding_service.generate_profile_embedding({
        "headline": profile.headline,
        "summary": profile.summary,
        "validated_json": profile.validated_json
    })
    
    candidate_jobs = []
    if profile_embedding:
        # Vector similarity search
        similar_jobs = milvus_service.search_similar_jobs(profile_embedding, top_k=100)
        candidate_jobs = [r["job_id"] for r in similar_jobs]
    
    # Step 2: Get user skills
    user_skills = db.execute(
        select(ProfileSkill, Skill)
        .join(Skill)
        .where(ProfileSkill.profile_id == profile.id)
    ).all()
    
    user_skill_ids = {ps.ProfileSkill.skill_id for ps in user_skills}
    user_skill_levels = {
        ps.ProfileSkill.skill_id: ps.ProfileSkill.proficiency_level 
        for ps in user_skills
    }
    
    # Step 3: Score and rank jobs
    scored_jobs = []
    
    # Get jobs (from vector search or all active)
    if candidate_jobs:
        jobs = db.execute(
            select(Job).where(Job.id.in_(candidate_jobs)).where(Job.is_active == True)
        ).scalars().all()
    else:
        # Fallback: get recent active jobs
        jobs = db.execute(
            select(Job)
            .where(Job.is_active == True)
            .order_by(Job.posted_at.desc())
            .limit(100)
        ).scalars().all()
    
    for job in jobs:
        # Get job skills
        job_skills = db.execute(
            select(JobSkill).where(JobSkill.job_id == job.id)
        ).scalars().all()
        
        job_skill_ids = {js.skill_id for js in job_skills}
        required_skills = {js.skill_id for js in job_skills if js.requirement_type == "required"}
        
        # Calculate skill match score
        if job_skill_ids:
            matched = user_skill_ids & job_skill_ids
            skill_match_score = (len(matched) / len(job_skill_ids)) * 100
        else:
            skill_match_score = 50  # Neutral if no skills defined
        
        # Calculate experience match score
        exp_match_score = 100
        if job.experience_min_years and profile.years_experience:
            if profile.years_experience >= job.experience_min_years:
                exp_match_score = 100
            else:
                gap = job.experience_min_years - profile.years_experience
                exp_match_score = max(0, 100 - (gap * 20))
        
        # Calculate location match score
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
        
        # Get semantic similarity (from vector search)
        semantic_sim = 0.5
        for r in (similar_jobs if candidate_jobs else []):
            if r.get("job_id") == job.id:
                semantic_sim = r.get("similarity", 0.5)
                break
        
        # Calculate overall match score
        match_score = (
            skill_match_score * 0.40 +
            exp_match_score * 0.25 +
            loc_match_score * 0.15 +
            (semantic_sim * 100) * 0.20
        )
        
        # Identify matched and missing skills
        matched_skills = list(user_skill_ids & job_skill_ids)
        missing_skills = list(required_skills - user_skill_ids)
        
        scored_jobs.append({
            "job": job,
            "match_score": match_score,
            "skill_match_score": skill_match_score,
            "experience_match_score": exp_match_score,
            "location_match_score": loc_match_score,
            "semantic_similarity": semantic_sim,
            "matched_skills": matched_skills,
            "missing_skills": missing_skills
        })
    
    # Sort by match score
    scored_jobs.sort(key=lambda x: x["match_score"], reverse=True)
    
    # Save recommendations
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
            missing_skills={"skill_ids": scored["missing_skills"]}
        )
        db.add(rec)
        recommendations.append(rec)
    
    db.commit()
    
    return _format_recommendations(recommendations, db)


def _format_recommendations(recommendations: List[Recommendation], db: Session) -> dict:
    """Format recommendations for response."""
    results = []
    for rec in recommendations:
        job = db.get(Job, rec.job_id)
        if job:
            # Get skill names for matched/missing
            matched_names = []
            missing_names = []
            
            if rec.matched_skills and rec.matched_skills.get("skill_ids"):
                for sid in rec.matched_skills["skill_ids"][:5]:
                    skill = db.get(Skill, sid)
                    if skill:
                        matched_names.append(skill.name)
            
            if rec.missing_skills and rec.missing_skills.get("skill_ids"):
                for sid in rec.missing_skills["skill_ids"][:5]:
                    skill = db.get(Skill, sid)
                    if skill:
                        missing_names.append(skill.name)
            
            results.append({
                "id": rec.id,
                "job": {
                    "id": job.id,
                    "title": job.title,
                    "company_name": job.company_name,
                    "location_city": job.location_city,
                    "location_type": job.location_type,
                    "salary_min": job.salary_min,
                    "salary_max": job.salary_max
                },
                "match_score": round(rec.match_score, 1),
                "skill_match_score": round(rec.skill_match_score, 1),
                "experience_match_score": round(rec.experience_match_score, 1),
                "location_match_score": round(rec.location_match_score, 1),
                "ranking_position": rec.ranking_position,
                "matched_skills": matched_names,
                "missing_skills": missing_names,
                "is_viewed": rec.is_viewed,
                "user_feedback": rec.user_feedback
            })
    
    return {"recommendations": results, "count": len(results)}


@router.post("/{recommendation_id}/feedback")
async def submit_feedback(
    recommendation_id: int,
    feedback: str = Query(..., regex="^(interested|not_interested|applied|saved)$"),
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit feedback on a recommendation.
    """
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


@router.post("/{recommendation_id}/view")
async def mark_viewed(
    recommendation_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark a recommendation as viewed.
    """
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


@router.get("/skill-gaps")
async def get_skill_gaps(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get skill gap analysis based on target jobs.
    """
    # Get existing gaps
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
                    "priority_score": g.SkillGap.priority_score,
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
    
    # Aggregate missing skills
    skill_frequency = {}
    for rec in recommendations:
        if rec.missing_skills and rec.missing_skills.get("skill_ids"):
            for skill_id in rec.missing_skills["skill_ids"]:
                skill_frequency[skill_id] = skill_frequency.get(skill_id, 0) + 1
    
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
    
    # Create skill gaps
    new_gaps = []
    for skill_id, frequency in sorted(skill_frequency.items(), key=lambda x: x[1], reverse=True)[:10]:
        skill = db.get(Skill, skill_id)
        if not skill:
            continue
        
        current_level = user_skill_levels.get(skill_id, "none")
        gap_type = "missing" if current_level == "none" else "insufficient"
        
        priority_score = min(100, frequency * 10 + skill.popularity_score * 0.5)
        
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
    
    db.commit()
    
    return {
        "skill_gaps": [
            {
                "id": g[0].id,
                "skill_name": g[1].name,
                "skill_type": g[1].skill_type,
                "gap_type": g[0].gap_type,
                "current_level": g[0].current_level,
                "target_level": g[0].target_level,
                "priority_score": g[0].priority_score,
                "frequency_in_jobs": g[0].frequency_in_jobs
            }
            for g in new_gaps
        ]
    }


@router.get("/learning-path")
async def get_learning_path(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get personalized learning path based on skill gaps.
    """
    # Get skill gaps
    gaps = db.execute(
        select(SkillGap)
        .where(SkillGap.user_id == current_user.user_id)
        .where(SkillGap.is_addressed == False)
        .order_by(SkillGap.priority_score.desc())
        .limit(5)
    ).scalars().all()
    
    if not gaps:
        return {"learning_path": [], "message": "No skill gaps found. Run skill gap analysis first."}
    
    # Find learning resources for each gap
    path_items = []
    sequence = 1
    
    for gap in gaps:
        skill = db.get(Skill, gap.skill_id)
        
        # Find resources for this skill
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



@router.get("/ai-learning-path")
async def get_ai_learning_path(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get AI-powered personalized learning recommendations.
    Uses multiple AI agents to analyze skills and recommend learning topics.
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

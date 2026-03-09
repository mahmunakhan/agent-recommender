"""
Skills Router
Skill taxonomy management and search
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from typing import List, Optional

from app.services.database import get_db
from app.models import Skill, SkillCategory, SkillAlias

router = APIRouter(prefix="/skills", tags=["Skills"])


@router.get("/")
async def list_skills(
    category: Optional[str] = None,
    skill_type: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    List all skills with optional filtering.
    """
    query = select(Skill).where(Skill.is_verified == True)
    
    # Filter by category
    if category:
        query = query.join(SkillCategory).where(SkillCategory.slug == category)
    
    # Filter by type
    if skill_type:
        query = query.where(Skill.skill_type == skill_type)
    
    # Search by name
    if search:
        query = query.where(Skill.name.ilike(f"%{search}%"))
    
    # Order by popularity
    query = query.order_by(Skill.popularity_score.desc())
    
    # Pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    
    skills = db.execute(query).scalars().all()
    
    return {
        "skills": [
            {
                "id": s.id,
                "name": s.name,
                "slug": s.slug,
                "skill_type": s.skill_type,
                "category_id": s.category_id,
                "popularity_score": s.popularity_score,
                "trending_score": s.trending_score
            }
            for s in skills
        ],
        "page": page,
        "page_size": page_size
    }


@router.get("/categories")
async def list_categories(db: Session = Depends(get_db)):
    """
    List all skill categories in hierarchy.
    """
    # Get root categories
    root_cats = db.execute(
        select(SkillCategory)
        .where(SkillCategory.parent_id == None)
        .where(SkillCategory.is_active == True)
        .order_by(SkillCategory.display_order)
    ).scalars().all()
    
    def build_tree(category):
        children = db.execute(
            select(SkillCategory)
            .where(SkillCategory.parent_id == category.id)
            .where(SkillCategory.is_active == True)
            .order_by(SkillCategory.display_order)
        ).scalars().all()
        
        return {
            "id": category.id,
            "name": category.name,
            "slug": category.slug,
            "level": category.level,
            "icon": category.icon,
            "children": [build_tree(c) for c in children]
        }
    
    return {"categories": [build_tree(cat) for cat in root_cats]}


@router.get("/search")
async def search_skills(
    q: str = Query(..., min_length=2),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Search skills by name or alias.
    """
    # Search in skill names
    skill_results = db.execute(
        select(Skill)
        .where(Skill.name.ilike(f"%{q}%"))
        .order_by(Skill.popularity_score.desc())
        .limit(limit)
    ).scalars().all()
    
    # Search in aliases
    alias_results = db.execute(
        select(SkillAlias)
        .where(SkillAlias.alias.ilike(f"%{q}%"))
        .limit(limit)
    ).scalars().all()
    
    # Combine results
    skill_ids = {s.id for s in skill_results}
    results = list(skill_results)
    
    for alias in alias_results:
        if alias.skill_id not in skill_ids:
            skill = db.get(Skill, alias.skill_id)
            if skill:
                results.append(skill)
                skill_ids.add(skill.id)
    
    return {
        "query": q,
        "results": [
            {
                "id": s.id,
                "name": s.name,
                "slug": s.slug,
                "skill_type": s.skill_type,
                "popularity_score": s.popularity_score
            }
            for s in results[:limit]
        ]
    }


@router.get("/{skill_id}")
async def get_skill(skill_id: str, db: Session = Depends(get_db)):
    """
    Get skill details including aliases.
    """
    skill = db.get(Skill, skill_id)
    
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    
    # Get aliases
    aliases = db.execute(
        select(SkillAlias).where(SkillAlias.skill_id == skill_id)
    ).scalars().all()
    
    # Get category
    category = db.get(SkillCategory, skill.category_id)
    
    return {
        "id": skill.id,
        "name": skill.name,
        "slug": skill.slug,
        "description": skill.description,
        "skill_type": skill.skill_type,
        "popularity_score": skill.popularity_score,
        "trending_score": skill.trending_score,
        "category": {
            "id": category.id,
            "name": category.name,
            "path": category.path
        } if category else None,
        "aliases": [
            {
                "alias": a.alias,
                "type": a.alias_type
            }
            for a in aliases
        ]
    }


@router.get("/popular/top")
async def get_popular_skills(
    limit: int = Query(20, ge=1, le=50),
    skill_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get top skills by popularity.
    """
    query = select(Skill).where(Skill.is_verified == True)
    
    if skill_type:
        query = query.where(Skill.skill_type == skill_type)
    
    query = query.order_by(Skill.popularity_score.desc()).limit(limit)
    
    skills = db.execute(query).scalars().all()
    
    return {
        "skills": [
            {
                "id": s.id,
                "name": s.name,
                "skill_type": s.skill_type,
                "popularity_score": s.popularity_score,
                "trending_score": s.trending_score
            }
            for s in skills
        ]
    }
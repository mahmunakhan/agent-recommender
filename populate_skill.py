"""
COMPLETE SKILL POPULATION SCRIPT (Robust Version)
===================================================
Run from project root:  python populate_skills.py

This script handles EVERYTHING in one go:
  1. Seeds skill_categories (if empty)
  2. Creates skills from profile parsed_json_draft
  3. Links profile_skills
  4. Creates skills from job requirements_json
  5. Links job_skills
  6. Handles all edge cases (enums, duplicates, nulls)

Works on fresh database or existing one (idempotent - safe to re-run).
"""

import os
import re
import sys
import json
import uuid
from datetime import datetime

# ══════════════════════════════════════════════════════════════
# DATABASE CONNECTION — Update if needed
# ══════════════════════════════════════════════════════════════

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+mysqlconnector://jobuser:jobpassword123@localhost:3306/job_recommendation"
)

from sqlalchemy import create_engine, select, text
from sqlalchemy import Column, String, Boolean, Float, Integer, Text
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()


# ══════════════════════════════════════════════════════════════
# MINIMAL MODELS
# ══════════════════════════════════════════════════════════════

class SkillCategory(Base):
    __tablename__ = "skill_categories"
    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), nullable=False, unique=True)
    parent_id = Column(String(36), nullable=True)
    description = Column(Text, nullable=True)
    icon = Column(String(50), nullable=True)
    display_order = Column(Integer, default=0)
    level = Column(Integer, default=0)
    path = Column(String(500), nullable=False)
    is_active = Column(Boolean, default=True)


class Skill(Base):
    __tablename__ = "skills"
    id = Column(String(36), primary_key=True)
    name = Column(String(200), nullable=False)
    slug = Column(String(200))
    category_id = Column(String(50))
    skill_type = Column(String(50))
    is_verified = Column(Boolean, default=True)


class ProfileSkill(Base):
    __tablename__ = "profile_skills"
    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(String(36), nullable=False)
    skill_id = Column(String(36), nullable=False)
    proficiency_level = Column(String(50), default="intermediate")
    years_experience = Column(Float, nullable=True)
    is_primary = Column(Boolean, default=False)
    source = Column(String(50), default="parsed")


class JobSkill(Base):
    __tablename__ = "job_skills"
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(36), nullable=False)
    skill_id = Column(String(36), nullable=False)
    requirement_type = Column(String(50), default="required")
    min_years = Column(Integer, nullable=True)
    confidence_score = Column(Float, default=0.85)


# ══════════════════════════════════════════════════════════════
# CONSTANTS & MAPPINGS
# ══════════════════════════════════════════════════════════════

CATEGORIES_SEED = [
    ("cat-prog-lang", "Programming Languages", "programming-languages", "Programming languages", 1),
    ("cat-ml", "Machine Learning & AI", "machine-learning-ai", "ML and AI skills", 2),
    ("cat-frameworks", "Frameworks & Libraries", "frameworks-libraries", "Frameworks and libraries", 3),
    ("cat-cloud-plat", "Cloud Platforms", "cloud-platforms", "Cloud platforms", 4),
    ("cat-databases", "Databases", "databases", "Database technologies", 5),
    ("cat-cicd", "DevOps & CI/CD", "devops-cicd", "DevOps and CI/CD tools", 6),
    ("cat-data-eng", "Data Engineering", "data-engineering", "Data engineering tools", 7),
    ("cat-data-viz", "Data Visualization", "data-visualization", "Visualization tools", 8),
    ("cat-genai", "Generative AI", "generative-ai", "GenAI and LLM tools", 9),
    ("cat-nlp", "NLP", "nlp", "Natural language processing", 10),
    ("cat-cv", "Computer Vision", "computer-vision", "Computer vision", 11),
    ("cat-dl", "Deep Learning", "deep-learning", "Deep learning", 12),
    ("cat-agile", "Methodologies", "methodologies", "Agile, Scrum, etc.", 13),
    ("cat-soft", "Soft Skills", "soft-skills", "Communication, leadership, etc.", 14),
    ("cat-infra", "Infrastructure", "infrastructure", "Infrastructure and automation", 15),
    ("cat-containers", "Containers", "containers", "Container technologies", 16),
    ("cat-mlops", "MLOps", "mlops", "ML operations", 17),
    ("cat-pm", "Project Management", "project-management", "PM tools and skills", 18),
    ("cat-api", "APIs", "apis", "API frameworks", 19),
]

TOOL_NAMES = {
    'docker', 'kubernetes', 'k8s', 'aws', 'azure', 'gcp', 'google cloud',
    'terraform', 'ansible', 'jenkins', 'github actions', 'gitlab ci',
    'git', 'github', 'jira', 'postman', 'grafana', 'prometheus', 'datadog',
    'tableau', 'power bi', 'powerbi', 'excel', 'mongodb', 'postgresql',
    'postgres', 'mysql', 'redis', 'elasticsearch', 'kafka', 'rabbitmq',
    'airflow', 'mlflow', 'dbt', 'snowflake', 'bigquery', 'spark', 'hadoop',
    'hive', 'pinecone', 'chroma', 'chromadb', 'faiss', 'milvus', 'weaviate',
    'linux', 'nginx', 'figma', 'neo4j', 'dynamodb',
    'firebase', 'supabase', 'vercel', 'heroku', 'sagemaker', 'vertex ai',
    'bedrock', 'databricks', 'n8n', 'zapier', 'make',
    'jupyter notebook', 'opencv', 'plotly', 'fastapi', 'autogen',
    'mlops', 'streamlit', 'ollama', 'groq',
    'hugging face', 'openai api', 'openai', 'google cloud platform',
    'vs code', 'visual studio code', 'incorta', 'sas',
}

CATEGORY_MAP = {
    'skills_technologies': 'cat-ml',
    'tools_platforms': 'cat-frameworks',
    'programming_language': 'cat-prog-lang',
    'programming_languages': 'cat-prog-lang',
    'ai_ml': 'cat-ml',
    'ml_framework': 'cat-frameworks',
    'cloud_platform': 'cat-cloud-plat',
    'database': 'cat-databases',
    'devops': 'cat-cicd',
    'data_engineering': 'cat-data-eng',
    'frontend': 'cat-frameworks',
    'backend': 'cat-frameworks',
    'visualization': 'cat-data-viz',
    'vector_database': 'cat-databases',
    'ai_tools': 'cat-genai',
    'ai_agents': 'cat-genai',
    'ai_techniques': 'cat-genai',
    'computer_vision': 'cat-cv',
    'nlp': 'cat-nlp',
    'deep_learning': 'cat-dl',
    'methodology': 'cat-agile',
    'soft_skill': 'cat-soft',
    'automation': 'cat-infra',
    'containers': 'cat-containers',
    'mlops': 'cat-mlops',
    'pm': 'cat-pm',
    'api_framework': 'cat-api',
    'technical': 'cat-ml',
    'tool': 'cat-frameworks',
    'skill': 'cat-ml',
    'other': 'cat-ml',
}

# Maps any importance/requirement string to valid DB ENUM values
REQUIREMENT_TYPE_MAP = {
    'critical': 'required',
    'high': 'required',
    'medium': 'preferred',
    'low': 'nice_to_have',
    'required': 'required',
    'preferred': 'preferred',
    'nice_to_have': 'nice_to_have',
    'optional': 'nice_to_have',
    'bonus': 'nice_to_have',
}


# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════

def make_slug(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    return slug.strip('-')[:100]


def safe_json(raw):
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return None
    return None


def normalize_requirement_type(raw_type: str) -> str:
    if not raw_type:
        return "required"
    return REQUIREMENT_TYPE_MAP.get(raw_type.lower().strip(), "required")


def find_or_create_skill(session, skill_name: str, category: str = "technical") -> str:
    if not skill_name or len(skill_name.strip()) < 2 or len(skill_name.strip()) > 60:
        return None

    skill_name = skill_name.strip()

    # Exact match (case-insensitive)
    existing = session.execute(
        select(Skill).where(Skill.name.ilike(skill_name))
    ).scalar_one_or_none()

    if existing:
        return existing.id

    # Create new skill
    category_id = CATEGORY_MAP.get(category, "cat-ml")
    skill_type = "tool" if skill_name.lower() in TOOL_NAMES else "technical"

    skill = Skill(
        id=str(uuid.uuid4()),
        name=skill_name,
        slug=make_slug(skill_name),
        category_id=category_id,
        skill_type=skill_type,
        is_verified=True,
    )
    session.add(skill)
    session.flush()
    return skill.id


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  COMPLETE SKILL POPULATION SCRIPT")
    print("=" * 60)

    engine = create_engine(DATABASE_URL, echo=False)
    Session = sessionmaker(bind=engine)
    session = Session()

    # ──────────────────────────────────────────────────────────
    # STEP 0: Seed skill_categories
    # ──────────────────────────────────────────────────────────
    print("\n🏷️  STEP 0: Checking skill_categories...")

    existing_ids = set(
        r[0] for r in session.execute(text("SELECT id FROM skill_categories")).fetchall()
    )

    added_cats = 0
    for cat_id, name, slug, desc, order in CATEGORIES_SEED:
        if cat_id not in existing_ids:
            cat = SkillCategory(
                id=cat_id, name=name, slug=slug, description=desc,
                display_order=order, level=0, path=slug, is_active=True,
            )
            session.add(cat)
            added_cats += 1

    if added_cats:
        session.commit()
        print(f"   ✅ Seeded {added_cats} categories")
    else:
        print(f"   ✅ All {len(existing_ids)} categories already present")

    # ──────────────────────────────────────────────────────────
    # STEP 1: Process ALL profiles
    # ──────────────────────────────────────────────────────────
    print("\n📋 STEP 1: Processing profiles...")

    profiles = session.execute(text(
        "SELECT id, parsed_json_draft FROM profiles WHERE parsed_json_draft IS NOT NULL"
    )).fetchall()

    print(f"   Found {len(profiles)} profiles with parsed data")
    total_profile_skills = 0

    for profile_id, parsed_raw in profiles:
        parsed = safe_json(parsed_raw)
        if not parsed:
            print(f"   ⚠️  Profile {str(profile_id)[:8]}... — invalid JSON, skipping")
            continue

        skills_data = parsed.get("skills", {})
        skill_names = []

        if isinstance(skills_data, dict):
            for cat, items in skills_data.items():
                if cat in ("skill_proficiency", "meta"):
                    continue
                if isinstance(items, list):
                    for name in items:
                        if isinstance(name, str) and name.strip():
                            skill_names.append((name.strip(), cat))
                        elif isinstance(name, dict) and name.get("name"):
                            skill_names.append((name["name"].strip(), cat))
        elif isinstance(skills_data, list):
            for s in skills_data:
                if isinstance(s, dict) and s.get("name"):
                    skill_names.append((s["name"].strip(), "technical"))
                elif isinstance(s, str) and s.strip():
                    skill_names.append((s.strip(), "technical"))

        print(f"   Profile {str(profile_id)[:8]}... → {len(skill_names)} skills found")

        profile_added = 0
        for skill_name, cat in skill_names:
            try:
                skill_id = find_or_create_skill(session, skill_name, cat)
                if not skill_id:
                    continue

                existing_link = session.execute(
                    select(ProfileSkill).where(
                        ProfileSkill.profile_id == str(profile_id),
                        ProfileSkill.skill_id == skill_id
                    )
                ).scalar_one_or_none()

                if not existing_link:
                    ps = ProfileSkill(
                        profile_id=str(profile_id),
                        skill_id=skill_id,
                        proficiency_level="intermediate",
                        is_primary=False,
                        source="parsed",
                    )
                    session.add(ps)
                    profile_added += 1

            except Exception as e:
                session.rollback()
                print(f"   ⚠️  Error with skill '{skill_name}': {e}")
                continue

        try:
            session.commit()
            total_profile_skills += profile_added
            print(f"   ✅ Linked {profile_added} skills")
        except Exception as e:
            session.rollback()
            print(f"   ❌ Commit failed: {e}")

    print(f"\n   ✅ Total profile_skills linked: {total_profile_skills}")

    # ──────────────────────────────────────────────────────────
    # STEP 2: Process ALL jobs
    # ──────────────────────────────────────────────────────────
    print("\n📋 STEP 2: Processing jobs...")

    jobs = session.execute(text(
        "SELECT id, title, requirements_json FROM jobs WHERE requirements_json IS NOT NULL"
    )).fetchall()

    print(f"   Found {len(jobs)} jobs with requirements")
    total_job_skills = 0

    for row in jobs:
        job_id = row[0]
        job_title = row[1] or "Unknown"
        req_raw = row[2]

        req = safe_json(req_raw)
        if not req:
            print(f"   ⚠️  Job '{job_title}' — invalid JSON, skipping")
            continue

        required_skills = req.get("required_skills", [])
        preferred_skills = req.get("preferred_skills", [])
        all_job_skills = []

        # Parse required_skills (structured objects)
        for s in required_skills:
            if not isinstance(s, dict) or not s.get("skill_name"):
                continue

            raw_name = s["skill_name"]
            importance = normalize_requirement_type(s.get("importance", "required"))
            min_years = s.get("min_years")

            # Handle compound: "ML frameworks (scikit-learn, XGBoost, PyTorch)"
            paren_match = re.search(r'\(([^)]+)\)', raw_name)
            if paren_match:
                main_name = raw_name[:raw_name.index('(')].strip().rstrip(',')
                if main_name and len(main_name) > 2:
                    all_job_skills.append({"name": main_name, "type": importance, "min_years": min_years})
                for sub in paren_match.group(1).split(","):
                    sub = sub.strip()
                    if sub and len(sub) > 1:
                        all_job_skills.append({"name": sub, "type": importance, "min_years": min_years})
            else:
                all_job_skills.append({"name": raw_name, "type": importance, "min_years": min_years})

        # Parse preferred_skills (string list or objects)
        for s in preferred_skills:
            if isinstance(s, str) and s.strip():
                all_job_skills.append({"name": s.strip(), "type": "preferred", "min_years": None})
            elif isinstance(s, dict) and s.get("name"):
                all_job_skills.append({
                    "name": s["name"].strip(),
                    "type": normalize_requirement_type(s.get("importance", "preferred")),
                    "min_years": s.get("min_years"),
                })

        print(f"   Job '{job_title}' ({str(job_id)[:8]}...) → {len(all_job_skills)} skills")

        job_added = 0
        for skill_info in all_job_skills:
            try:
                skill_name = skill_info["name"]
                skill_id = find_or_create_skill(session, skill_name, "technical")
                if not skill_id:
                    continue

                existing_link = session.execute(
                    select(JobSkill).where(
                        JobSkill.job_id == str(job_id),
                        JobSkill.skill_id == skill_id
                    )
                ).scalar_one_or_none()

                if not existing_link:
                    js = JobSkill(
                        job_id=str(job_id),
                        skill_id=skill_id,
                        requirement_type=normalize_requirement_type(skill_info.get("type", "required")),
                        min_years=skill_info.get("min_years"),
                        confidence_score=0.85,
                    )
                    session.add(js)
                    job_added += 1

            except Exception as e:
                session.rollback()
                print(f"   ⚠️  Error with skill '{skill_info.get('name', '?')}': {e}")
                continue

        try:
            session.commit()
            total_job_skills += job_added
            print(f"   ✅ Linked {job_added} skills")
        except Exception as e:
            session.rollback()
            print(f"   ❌ Commit failed: {e}")

    print(f"\n   ✅ Total job_skills linked: {total_job_skills}")

    # ──────────────────────────────────────────────────────────
    # SUMMARY
    # ──────────────────────────────────────────────────────────
    cat_count = session.execute(text("SELECT COUNT(*) FROM skill_categories")).scalar()
    skill_count = session.execute(text("SELECT COUNT(*) FROM skills")).scalar()
    ps_count = session.execute(text("SELECT COUNT(*) FROM profile_skills")).scalar()
    js_count = session.execute(text("SELECT COUNT(*) FROM job_skills")).scalar()

    print("\n" + "=" * 60)
    print("  ✅ MIGRATION COMPLETE — SUMMARY")
    print("=" * 60)
    print(f"   Skill categories:      {cat_count}")
    print(f"   Skills in taxonomy:     {skill_count}")
    print(f"   Profile-skill links:    {ps_count}")
    print(f"   Job-skill links:        {js_count}")

    print("\n   📊 Sample profile skills:")
    samples = session.execute(text(
        "SELECT s.name, ps.proficiency_level FROM profile_skills ps "
        "JOIN skills s ON ps.skill_id = s.id LIMIT 5"
    )).fetchall()
    for name, level in samples:
        print(f"      • {name} ({level})")

    print("\n   📊 Sample job skills:")
    samples = session.execute(text(
        "SELECT s.name, js.requirement_type FROM job_skills js "
        "JOIN skills s ON js.skill_id = s.id LIMIT 5"
    )).fetchall()
    for name, rtype in samples:
        print(f"      • {name} ({rtype})")

    print("\n   NEXT STEPS:")
    print("   1. Replace _sync_profile_skills in profiles.py (see fix file)")
    print("   2. Restart backend")
    print("   3. Re-run matching from frontend")
    print("   4. Skill gaps should now populate")
    print("=" * 60)

    session.close()


if __name__ == "__main__":
    main()
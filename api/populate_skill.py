"""
ONE-TIME MIGRATION SCRIPT: Populate skills, profile_skills, and job_skills
===========================================================================

Run this ONCE from your project root (where your api/ folder is):
    python populate_skills.py

This script:
  1. Reads parsed_json_draft from ALL profiles → creates skills → links profile_skills
  2. Reads requirements_json from ALL jobs → creates skills → links job_skills
  3. Shows a summary of what was created

IMPORTANT: 
  - Update the DATABASE_URL below to match your .env
  - Make sure MySQL is running before you run this
"""

import os
import re
import sys
import json
import uuid
from datetime import datetime

# ── Update this to match YOUR database connection ──
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+mysqlconnector://root:password@localhost:3306/job_recommendation"
)

# If you use a .env file, uncomment these lines:
# from dotenv import load_dotenv
# load_dotenv(".env.local")
# DATABASE_URL = os.getenv("DATABASE_URL")

from sqlalchemy import create_engine, select, text, Column, String, Boolean, Float, Integer, ForeignKey, Text, DateTime, JSON
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()

# ─── Minimal models (just what we need) ───

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


# ─── Helpers ───

TOOL_NAMES = {
    'docker','kubernetes','k8s','aws','azure','gcp','google cloud',
    'terraform','ansible','jenkins','github actions','gitlab ci',
    'git','github','jira','postman','grafana','prometheus','datadog',
    'tableau','power bi','powerbi','excel','mongodb','postgresql',
    'postgres','mysql','redis','elasticsearch','kafka','rabbitmq',
    'airflow','mlflow','dbt','snowflake','bigquery','spark','hadoop',
    'hive','pinecone','chroma','chromadb','faiss','milvus','weaviate',
    'linux','nginx','figma','neo4j','dynamodb',
    'firebase','supabase','vercel','heroku','sagemaker','vertex ai',
    'bedrock','databricks','n8n','zapier',
    'jupyter notebook','opencv','plotly','fastapi','autogen',
    'mlops','power bi','streamlit','ollama','groq',
    'hugging face','openai api','postgresql','docker','github',
}

CATEGORY_MAP = {
    'skills_technologies': 'cat-ml',
    'tools_platforms': 'cat-frameworks',
    'programming_language': 'cat-prog-lang',
    'ai_ml': 'cat-ml',
    'ml_framework': 'cat-frameworks',
    'cloud_platform': 'cat-cloud-plat',
    'database': 'cat-databases',
    'devops': 'cat-cicd',
    'data_engineering': 'cat-data-eng',
    'frontend': 'cat-frameworks',
    'backend': 'cat-frameworks',
    'visualization': 'cat-data-viz',
    'methodology': 'cat-agile',
    'soft_skill': 'cat-soft',
    'other': 'cat-ml',
    'technical': 'cat-ml',
    'tool': 'cat-frameworks',
}

def make_slug(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    return slug.strip('-')[:100]


def find_or_create_skill(session, skill_name: str, category: str = "technical") -> str:
    """Find skill by name or create it. Returns skill_id."""
    if not skill_name or len(skill_name) < 2 or len(skill_name) > 60:
        return None

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


def main():
    print("=" * 60)
    print("SKILL POPULATION SCRIPT")
    print("=" * 60)

    engine = create_engine(DATABASE_URL, echo=False)
    Session = sessionmaker(bind=engine)
    session = Session()

    stats = {
        "skills_created": 0,
        "profile_skills_linked": 0,
        "job_skills_linked": 0,
    }

    # ═══════════════════════════════════════════════════════════
    # STEP 1: Process ALL profiles
    # ═══════════════════════════════════════════════════════════
    print("\n📋 STEP 1: Processing profiles...")

    rows = session.execute(text(
        "SELECT id, parsed_json_draft FROM profiles WHERE parsed_json_draft IS NOT NULL"
    )).fetchall()

    print(f"   Found {len(rows)} profiles with parsed data")

    for profile_id, parsed_raw in rows:
        # Parse the JSON
        if isinstance(parsed_raw, str):
            try:
                parsed = json.loads(parsed_raw)
            except:
                continue
        elif isinstance(parsed_raw, dict):
            parsed = parsed_raw
        else:
            continue

        skills_data = parsed.get("skills", {})
        skill_names = []

        if isinstance(skills_data, dict):
            for cat, items in skills_data.items():
                if cat == "skill_proficiency":
                    continue
                if isinstance(items, list):
                    for name in items:
                        if isinstance(name, str) and name.strip():
                            skill_names.append((name.strip(), cat))
        elif isinstance(skills_data, list):
            for s in skills_data:
                if isinstance(s, dict) and s.get("name"):
                    skill_names.append((s["name"].strip(), "technical"))

        print(f"   Profile {profile_id[:8]}... → {len(skill_names)} skills found")

        for skill_name, cat in skill_names:
            skill_id = find_or_create_skill(session, skill_name, cat)
            if not skill_id:
                continue

            # Check if we just created it
            is_new = session.new  # rough check
            if skill_id:
                stats["skills_created"] += len([o for o in session.new if isinstance(o, Skill)])

            # Check if link exists
            existing_link = session.execute(
                select(ProfileSkill).where(
                    ProfileSkill.profile_id == profile_id,
                    ProfileSkill.skill_id == skill_id
                )
            ).scalar_one_or_none()

            if not existing_link:
                ps = ProfileSkill(
                    profile_id=profile_id,
                    skill_id=skill_id,
                    proficiency_level="intermediate",
                    is_primary=False,
                    source="parsed",
                )
                session.add(ps)
                stats["profile_skills_linked"] += 1

    session.commit()
    print(f"   ✅ Profile skills linked: {stats['profile_skills_linked']}")

    # ═══════════════════════════════════════════════════════════
    # STEP 2: Process ALL jobs
    # ═══════════════════════════════════════════════════════════
    print("\n📋 STEP 2: Processing jobs...")

    rows = session.execute(text(
        "SELECT id, title, requirements_json FROM jobs WHERE requirements_json IS NOT NULL"
    )).fetchall()

    print(f"   Found {len(rows)} jobs with requirements")

    for job_id, job_title, req_raw in rows:
        if isinstance(req_raw, str):
            try:
                req = json.loads(req_raw)
            except:
                continue
        elif isinstance(req_raw, dict):
            req = req_raw
        else:
            continue

        required_skills = req.get("required_skills", [])
        preferred_skills = req.get("preferred_skills", [])

        all_job_skills = []

        # Required skills (structured)
        for s in required_skills:
            if isinstance(s, dict) and s.get("skill_name"):
                # Some skill_names are compound: "ML frameworks (scikit-learn, XGBoost, PyTorch, TensorFlow)"
                raw_name = s["skill_name"]
                # Extract individual skills from parenthetical
                paren_match = re.search(r'\(([^)]+)\)', raw_name)
                if paren_match:
                    # Add the main concept
                    main_name = raw_name[:raw_name.index('(')].strip()
                    if main_name and len(main_name) > 2:
                        all_job_skills.append({
                            "name": main_name,
                            "type": s.get("importance", "required"),
                            "min_years": s.get("min_years"),
                        })
                    # Add individual tools
                    for sub in paren_match.group(1).split(","):
                        sub = sub.strip()
                        if sub and len(sub) > 1:
                            all_job_skills.append({
                                "name": sub,
                                "type": s.get("importance", "required"),
                                "min_years": s.get("min_years"),
                            })
                else:
                    all_job_skills.append({
                        "name": raw_name,
                        "type": s.get("importance", "required"),
                        "min_years": s.get("min_years"),
                    })

        # Preferred skills (simple list)
        for s in preferred_skills:
            if isinstance(s, str) and s.strip():
                all_job_skills.append({
                    "name": s.strip(),
                    "type": "preferred",
                    "min_years": None,
                })

        print(f"   Job '{job_title}' ({job_id[:8]}...) → {len(all_job_skills)} skills")

        for skill_info in all_job_skills:
            skill_name = skill_info["name"]
            skill_id = find_or_create_skill(session, skill_name, "technical")
            if not skill_id:
                continue

            # Check if link exists
            existing_link = session.execute(
                select(JobSkill).where(
                    JobSkill.job_id == job_id,
                    JobSkill.skill_id == skill_id
                )
            ).scalar_one_or_none()

            if not existing_link:
                js = JobSkill(
                    job_id=job_id,
                    skill_id=skill_id,
                    requirement_type=skill_info.get("type", "required"),
                    min_years=skill_info.get("min_years"),
                    confidence_score=0.85,
                )
                session.add(js)
                stats["job_skills_linked"] += 1

    session.commit()
    print(f"   ✅ Job skills linked: {stats['job_skills_linked']}")

    # ═══════════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════════
    skill_count = session.execute(text("SELECT COUNT(*) FROM skills")).scalar()
    ps_count = session.execute(text("SELECT COUNT(*) FROM profile_skills")).scalar()
    js_count = session.execute(text("SELECT COUNT(*) FROM job_skills")).scalar()

    print("\n" + "=" * 60)
    print("✅ MIGRATION COMPLETE")
    print("=" * 60)
    print(f"   Skills in taxonomy:    {skill_count}")
    print(f"   Profile-skill links:   {ps_count}")
    print(f"   Job-skill links:       {js_count}")
    print()
    print("NEXT STEPS:")
    print("  1. Replace _sync_profile_skills in profiles.py with the fixed version")
    print("  2. Restart your backend server")
    print("  3. Re-run matching to get proper missing_skills")
    print("  4. Skill gaps should now populate correctly")
    print("=" * 60)

    session.close()


if __name__ == "__main__":
    main()
    
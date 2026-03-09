"""
Job Skill Extractor - Multi-Agent System
==========================================
Implements the JobProcessingGraph from the technical specification.

Agents:
  1. SkillExtractorAgent - Uses Groq LLM to extract skills from job descriptions
  2. TaxonomyMatcherAgent - Maps extracted skills to canonical taxonomy
  3. RequirementClassifierAgent - Classifies skills as required/preferred/nice-to-have

Flow:
  Job Description → SkillExtractor → TaxonomyMatcher → RequirementClassifier → DB

Author: AI Job Recommendation Engine Team
"""

import os
import re
import json
import uuid
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime

logger = logging.getLogger(__name__)


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class ExtractedSkill:
    """A skill extracted by the LLM"""
    name: str
    category: str = ""
    requirement_type: str = "required"  # required, preferred, nice_to_have
    confidence: float = 0.0
    source: str = "llm"                 # llm, taxonomy, both
    taxonomy_id: Optional[str] = None
    canonical_name: Optional[str] = None
    min_years: Optional[int] = None
    proficiency_level: str = "intermediate"


@dataclass
class JobProcessingResult:
    """Result of processing a single job"""
    job_id: str
    job_title: str
    company: str
    skills_extracted: List[ExtractedSkill] = field(default_factory=list)
    skills_from_taxonomy: int = 0
    skills_from_llm: int = 0
    skills_merged: int = 0
    processing_time: float = 0.0
    errors: List[str] = field(default_factory=list)


# ============================================================================
# HELPER: Safe JSON parser
# ============================================================================

def safe_parse_json(text: str, default=None):
    if not text or not isinstance(text, str):
        return default if default is not None else {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for pattern in [r'```json\s*([\s\S]*?)\s*```', r'```\s*([\s\S]*?)\s*```']:
        match = re.search(pattern, text)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                continue
    for pattern in [r'\[[\s\S]*\]', r'\{[\s\S]*\}']:
        match = re.search(pattern, text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return default if default is not None else {}


# ============================================================================
# AGENT 1: SKILL EXTRACTOR (LLM-based)
# ============================================================================

class SkillExtractorAgent:
    """
    Uses Groq LLM to extract skills from job descriptions.
    Matches spec: JobParserAgent + SkillExtractor
    """

    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self.model = model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from groq import Groq
            self._client = Groq(api_key=self.api_key)
        return self._client

    def extract(self, job_title: str, company: str, description: str) -> List[ExtractedSkill]:
        """Extract skills from a job description using LLM"""
        logger.info(f"[SkillExtractor] Processing: {job_title} @ {company}")

        if not description or len(description.strip()) < 20:
            # No description available - infer from title
            return self._infer_from_title(job_title)

        prompt = f"""You are a job requirements analyst. Extract ALL technical skills, tools, and technologies required for this job.

JOB TITLE: {job_title}
COMPANY: {company}
DESCRIPTION: {description[:4000]}

RULES:
1. Extract ACTUAL skills (tools, technologies, programming languages, frameworks, methodologies)
2. Each skill should be SHORT (1-4 words max)
3. Classify each as: "required", "preferred", or "nice_to_have"
4. Assign a category: programming_language, ai_ml, ml_framework, cloud_platform, devops, database, data_engineering, frontend, backend, api_framework, visualization, methodology, soft_skill, other
5. Estimate minimum years of experience if mentioned
6. DO NOT include job titles, company names, or generic phrases

Return ONLY valid JSON array:
[{{"name": "Python", "category": "programming_language", "requirement_type": "required", "min_years": 3}},
 {{"name": "TensorFlow", "category": "ml_framework", "requirement_type": "preferred", "min_years": null}}]

JSON:"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a precise skill extraction agent. Return ONLY valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=2048
            )
            text = response.choices[0].message.content
            data = safe_parse_json(text, [])

            skills = []
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get('name'):
                        name = item['name'].strip()
                        if len(name) < 2 or len(name) > 40:
                            continue
                        skills.append(ExtractedSkill(
                            name=name,
                            category=item.get('category', 'other'),
                            requirement_type=item.get('requirement_type', 'required'),
                            confidence=0.85,
                            source='llm',
                            min_years=item.get('min_years'),
                        ))

            logger.info(f"[SkillExtractor] Extracted {len(skills)} skills from description")
            return skills

        except Exception as e:
            logger.error(f"[SkillExtractor] LLM error: {e}")
            return self._infer_from_title(job_title)

    def _infer_from_title(self, job_title: str) -> List[ExtractedSkill]:
        """When no description available, infer skills from job title using LLM"""
        logger.info(f"[SkillExtractor] No description, inferring from title: {job_title}")

        prompt = f"""Based on the job title below, list the most common required technical skills.

JOB TITLE: {job_title}

Return ONLY a JSON array of skills that are typically required for this role:
[{{"name": "Python", "category": "programming_language", "requirement_type": "required"}},
 {{"name": "Machine Learning", "category": "ai_ml", "requirement_type": "required"}}]

Include 5-10 most relevant skills. JSON:"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=1024
            )
            text = response.choices[0].message.content
            data = safe_parse_json(text, [])

            skills = []
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get('name'):
                        skills.append(ExtractedSkill(
                            name=item['name'].strip(),
                            category=item.get('category', 'other'),
                            requirement_type=item.get('requirement_type', 'preferred'),
                            confidence=0.70,  # lower confidence for inferred
                            source='llm_inferred',
                        ))

            logger.info(f"[SkillExtractor] Inferred {len(skills)} skills from title")
            return skills

        except Exception as e:
            logger.error(f"[SkillExtractor] Inference error: {e}")
            return []


# ============================================================================
# AGENT 2: TAXONOMY MATCHER
# ============================================================================

class TaxonomyMatcherAgent:
    """
    Maps LLM-extracted skills to canonical taxonomy entries.
    Matches spec: SkillNormalizerAgent
    """

    def __init__(self, taxonomy):
        self.taxonomy = taxonomy

    def match(self, extracted_skills: List[ExtractedSkill],
              job_description: str = "") -> List[ExtractedSkill]:
        """
        Match extracted skills against taxonomy and discover additional
        skills from text that the LLM might have missed.
        """
        # Phase 1: Match LLM skills against taxonomy
        matched = []
        seen_names = set()

        for skill in extracted_skills:
            entry = self.taxonomy.find_skill(skill.name)
            if entry:
                skill.taxonomy_id = entry.id
                skill.canonical_name = entry.name
                skill.source = 'both'
                skill.confidence = min(skill.confidence + 0.10, 1.0)
                if entry.category and entry.category != 'technical':
                    skill.category = entry.category
            matched.append(skill)
            seen_names.add(skill.name.lower())
            if skill.canonical_name:
                seen_names.add(skill.canonical_name.lower())

        # Phase 2: Find taxonomy skills in text that LLM missed
        if job_description:
            taxonomy_found = self.taxonomy.find_skills_in_text(job_description)
            for entry in taxonomy_found:
                if entry.name.lower() not in seen_names:
                    matched.append(ExtractedSkill(
                        name=entry.name,
                        category=entry.category,
                        requirement_type='preferred',
                        confidence=0.80,
                        source='taxonomy',
                        taxonomy_id=entry.id,
                        canonical_name=entry.name,
                    ))
                    seen_names.add(entry.name.lower())

        logger.info(f"[TaxonomyMatcher] {len(matched)} skills after matching "
                     f"({sum(1 for s in matched if s.source == 'both')} matched, "
                     f"{sum(1 for s in matched if s.source == 'taxonomy')} from taxonomy)")
        return matched


# ============================================================================
# AGENT 3: REQUIREMENT CLASSIFIER
# ============================================================================

class RequirementClassifierAgent:
    """
    Refines requirement classification based on job description context.
    Matches spec: RequirementClassifierAgent
    """

    REQUIRED_KEYWORDS = ['must have', 'required', 'essential', 'mandatory', 'minimum',
                         'need to have', 'should have experience in']
    PREFERRED_KEYWORDS = ['preferred', 'ideal', 'plus', 'advantageous', 'desirable',
                          'experience with', 'familiarity with']
    NICE_TO_HAVE_KEYWORDS = ['bonus', 'nice to have', 'optional', 'would be a plus',
                             'good to have', 'not required']

    def classify(self, skills: List[ExtractedSkill], description: str) -> List[ExtractedSkill]:
        """Refine requirement types based on description context"""
        if not description:
            return skills

        desc_lower = description.lower()

        for skill in skills:
            skill_lower = skill.name.lower()

            # Check surrounding context for requirement indicators
            # Look for skill mention in text and check nearby keywords
            idx = desc_lower.find(skill_lower)
            if idx == -1:
                continue

            # Get surrounding context (100 chars before and after)
            start = max(0, idx - 100)
            end = min(len(desc_lower), idx + len(skill_lower) + 100)
            context = desc_lower[start:end]

            # Classify based on context
            if any(kw in context for kw in self.REQUIRED_KEYWORDS):
                skill.requirement_type = 'required'
            elif any(kw in context for kw in self.NICE_TO_HAVE_KEYWORDS):
                skill.requirement_type = 'nice_to_have'
            elif any(kw in context for kw in self.PREFERRED_KEYWORDS):
                skill.requirement_type = 'preferred'

        return skills


# ============================================================================
# ORCHESTRATOR: JOB PROCESSING GRAPH
# ============================================================================

class JobProcessingGraph:
    """
    Orchestrates the multi-agent job skill extraction pipeline.

    Flow:
      Job → SkillExtractorAgent → TaxonomyMatcherAgent → RequirementClassifierAgent → Result
    """

    def __init__(self, taxonomy, api_key: str = None, model: str = None):
        self.extractor = SkillExtractorAgent(api_key=api_key, model=model)
        self.matcher = TaxonomyMatcherAgent(taxonomy)
        self.classifier = RequirementClassifierAgent()
        logger.info("🚀 JobProcessingGraph initialized (3 agents)")

    def process_job(self, job_id: str, job_title: str, company: str,
                    description: str = "") -> JobProcessingResult:
        """Process a single job through the multi-agent pipeline"""
        start = datetime.now()
        result = JobProcessingResult(job_id=job_id, job_title=job_title, company=company)

        try:
            # Agent 1: Extract skills via LLM
            llm_skills = self.extractor.extract(job_title, company, description)
            result.skills_from_llm = len(llm_skills)

            # Agent 2: Match against taxonomy + find additional skills
            matched_skills = self.matcher.match(llm_skills, description)
            result.skills_from_taxonomy = sum(1 for s in matched_skills if s.source in ('taxonomy', 'both'))

            # Agent 3: Refine requirement classification
            classified_skills = self.classifier.classify(matched_skills, description)

            # Deduplicate final list
            seen = set()
            final = []
            for skill in classified_skills:
                key = (skill.canonical_name or skill.name).lower()
                if key not in seen:
                    seen.add(key)
                    final.append(skill)

            result.skills_extracted = final
            result.skills_merged = len(final)

        except Exception as e:
            result.errors.append(str(e))
            logger.error(f"[JobProcessingGraph] Error: {e}")

        result.processing_time = (datetime.now() - start).total_seconds()
        logger.info(f"[JobProcessingGraph] {job_title}: {result.skills_merged} skills "
                     f"in {result.processing_time:.1f}s")
        return result

    def process_all_jobs(self, jobs: List[Dict]) -> List[JobProcessingResult]:
        """Process multiple jobs"""
        results = []
        for i, job in enumerate(jobs, 1):
            logger.info(f"\n{'='*50}")
            logger.info(f"Processing job {i}/{len(jobs)}: {job['title']} @ {job['company']}")
            logger.info(f"{'='*50}")
            result = self.process_job(
                job_id=job['id'],
                job_title=job['title'],
                company=job['company'],
                description=job.get('description', '')
            )
            results.append(result)
        return results


# ============================================================================
# DATABASE INTEGRATION
# ============================================================================

# Category mapping: taxonomy category → database category_id
CATEGORY_MAP = {
    'programming_language': 'cat-prog-lang',
    'ai_ml': 'cat-ml',
    'ml_framework': 'cat-frameworks',
    'cloud_platform': 'cat-cloud-plat',
    'devops': 'cat-cicd',
    'database': 'cat-databases',
    'data_engineering': 'cat-data-eng',
    'frontend': 'cat-frameworks',
    'backend': 'cat-frameworks',
    'api_framework': 'cat-api',
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
    'technical': 'cat-ml',   # fallback for generic technical
    'other': 'cat-ml',       # fallback
}

# Skill type mapping
SKILL_TYPE_MAP = {
    'programming_language': 'technical',
    'ai_ml': 'technical',
    'ml_framework': 'tool',
    'cloud_platform': 'tool',
    'devops': 'tool',
    'database': 'tool',
    'data_engineering': 'technical',
    'frontend': 'technical',
    'backend': 'technical',
    'api_framework': 'tool',
    'visualization': 'tool',
    'vector_database': 'tool',
    'ai_tools': 'tool',
    'ai_agents': 'tool',
    'ai_techniques': 'technical',
    'computer_vision': 'domain',
    'methodology': 'domain',
    'soft_skill': 'soft',
}


def _make_slug(name: str) -> str:
    """Generate slug from skill name: 'Machine Learning' -> 'machine-learning'"""
    import re
    slug = name.lower().strip()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    return slug.strip('-')[:100]


def save_skills_to_db(db_session, result: JobProcessingResult,
                      skill_model, job_skill_model) -> int:
    """
    Save extracted skills to the database.
    Creates skill entries if they don't exist, links them via job_skills.
    """
    from sqlalchemy import select

    saved = 0

    for extracted in result.skills_extracted:
        skill_name = extracted.canonical_name or extracted.name

        # Skip noisy extractions
        if len(skill_name) < 2 or len(skill_name) > 50:
            continue
        # Skip non-skill phrases
        skip_words = ['make', 'use', 'build', 'create', 'work', 'data-driven']
        if skill_name.lower() in skip_words or ' ' in skill_name and len(skill_name.split()) > 4:
            logger.info(f"  ⏭️ Skipping noisy extraction: {skill_name}")
            continue

        # 1. Find or create the skill in skills table
        existing = db_session.execute(
            select(skill_model).where(skill_model.name == skill_name)
        ).scalars().first()

        if not existing:
            # Map category to database category_id
            category_id = CATEGORY_MAP.get(extracted.category, 'cat-ml')
            skill_type = SKILL_TYPE_MAP.get(extracted.category, 'technical')
            slug = _make_slug(skill_name)

            new_skill = skill_model(
                id=str(uuid.uuid4()),
                name=skill_name,
                slug=slug,
                category_id=category_id,
                skill_type=skill_type,
                is_verified=True,
            )
            db_session.add(new_skill)
            db_session.flush()
            skill_id = new_skill.id
            logger.info(f"  + Created skill: {skill_name} → {category_id} ({skill_type})")
        else:
            skill_id = existing.id

        # 2. Check if job_skill link already exists
        existing_link = db_session.execute(
            select(job_skill_model).where(
                job_skill_model.job_id == result.job_id,
                job_skill_model.skill_id == skill_id
            )
        ).scalars().first()

        if not existing_link:
            # Create job_skill link
            job_skill = job_skill_model(
                job_id=result.job_id,
                skill_id=skill_id,
                requirement_type=extracted.requirement_type,
                min_years=extracted.min_years,
                confidence_score=extracted.confidence,
            )
            db_session.add(job_skill)
            saved += 1

    db_session.commit()
    logger.info(f"  ✅ Saved {saved} job-skill links for {result.job_title}")
    return saved
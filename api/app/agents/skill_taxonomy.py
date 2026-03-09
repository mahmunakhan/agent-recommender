"""
Skill Taxonomy Manager
======================
Adapted from ResumeParser v3.5 SkillTaxonomyManager.
Loads skills from O*NET, ESCO, and custom JSON sources.
Used by both Job and Resume processing agents.

Sources:
  - O*NET Technology Skills (32K+ entries)
  - ESCO Skills (104K+ entries)  
  - Custom skills JSON (250 emerging AI/ML skills)
  - Built-in defaults (80+ core tech skills)
"""

import os
import re
import csv
import json
import logging
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class SkillEntry:
    """Represents a skill in the taxonomy"""
    id: str
    name: str
    category: str
    source: str
    aliases: List[str] = field(default_factory=list)
    description: str = ""
    keywords: List[str] = field(default_factory=list)
    external_ids: Dict[str, str] = field(default_factory=dict)


# ============================================================================
# SKILL FILTER (from v3.5)
# ============================================================================

class SkillFilter:
    """Filters out invalid skills: course names, certs, generic phrases"""

    COURSE_INDICATORS = [
        'essentials', 'fundamentals', 'introduction', 'basics',
        'specialization', 'certification', 'certificate', 'certified',
        'bootcamp', 'workshop', 'training', 'course', 'program',
        'from the data center', 'path using', 'for business users',
        'for administrators', 'for developers', 'learning projects',
    ]

    NOT_SKILLS = [
        'deeplearning.ai', 'coursera', 'udemy', 'edx', 'linkedin learning',
        'google certified', 'microsoft certified', 'aws certified',
        'ibm certified', 'analyst certification'
    ]

    MAX_SKILL_LENGTH = 40

    @classmethod
    def is_valid_skill(cls, skill_name: str) -> bool:
        if not skill_name or len(skill_name.strip()) < 2:
            return False
        name_lower = skill_name.lower().strip()
        if len(skill_name) > cls.MAX_SKILL_LENGTH:
            return False
        for indicator in cls.COURSE_INDICATORS:
            if indicator in name_lower:
                return False
        for non_skill in cls.NOT_SKILLS:
            if non_skill in name_lower or name_lower in non_skill:
                return False
        if skill_name.count(' ') > 5:
            return False
        return True

    @classmethod
    def clean_skill_name(cls, name: str) -> str:
        name = re.sub(r'^(experience with|knowledge of|proficient in|skilled in)\s*', '', name, flags=re.IGNORECASE)
        name = re.sub(r'\s*(experience|knowledge|proficiency)$', '', name, flags=re.IGNORECASE)
        return name.strip()


# ============================================================================
# SKILL TAXONOMY MANAGER
# ============================================================================

class SkillTaxonomyManager:
    """
    Dynamic skill taxonomy from O*NET, ESCO, and custom sources.
    Provides fast lookup by name, alias, and keyword.
    """

    def __init__(self):
        self.skills: Dict[str, SkillEntry] = {}
        self.name_index: Dict[str, str] = {}      # lowercase name -> skill_id
        self.alias_index: Dict[str, str] = {}      # lowercase alias -> skill_id
        self.keyword_index: Dict[str, Set[str]] = {}
        self.categories: Dict[str, List[str]] = {}
        self._loaded_sources = []
        self._default_tech_skills = self._get_default_tech_skills()

    def load_all_sources(self,
                         onet_path: str = None,
                         esco_path: str = None,
                         custom_path: str = None):
        """Load skills from all configured sources"""
        onet_path = onet_path or os.getenv("ONET_SKILLS_PATH", "data/onet/Technology_Skills.txt")
        esco_path = esco_path or os.getenv("ESCO_SKILLS_PATH", "data/esco/skills_en.csv")
        custom_path = custom_path or os.getenv("CUSTOM_SKILLS_PATH", "data/custom_skills.json")

        loaded = False

        if os.path.exists(onet_path):
            self.load_onet(onet_path)
            loaded = True

        if os.path.exists(esco_path):
            self.load_esco(esco_path)
            loaded = True

        if os.path.exists(custom_path):
            self.load_custom(custom_path)
            loaded = True

        if not loaded:
            logger.warning("No external skill sources found. Using built-in defaults.")

        # Always load defaults to ensure core skills are present
        self._load_default_skills()

        logger.info(f"Skill taxonomy: {len(self.skills)} skills from {self._loaded_sources}")

    def load_onet(self, file_path: str):
        """Load O*NET Technology Skills"""
        try:
            skills_added = 0
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.reader(f, delimiter='\t')
                next(reader, None)  # skip header
                for row in reader:
                    if len(row) >= 3:
                        skill_name = row[2].strip() if len(row) > 2 else row[1].strip()
                        if not skill_name or len(skill_name) < 2:
                            continue
                        if not SkillFilter.is_valid_skill(skill_name):
                            continue
                        skill_id = f"onet_{self._normalize_id(skill_name)}"
                        if skill_id in self.skills:
                            continue
                        category = self._categorize_skill(skill_name)
                        if not self._is_tech_relevant(skill_name, category):
                            continue
                        entry = SkillEntry(
                            id=skill_id, name=skill_name, category=category,
                            source='onet', external_ids={'onet': row[0] if row else ''}
                        )
                        self._add_skill(entry)
                        skills_added += 1
            self._loaded_sources.append(f"O*NET ({skills_added})")
            logger.info(f"Loaded {skills_added} skills from O*NET")
        except Exception as e:
            logger.error(f"Failed to load O*NET: {e}")

    def load_esco(self, file_path: str):
        """Load ESCO Skills"""
        try:
            skills_added = 0
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    skill_name = row.get('preferredLabel', '').strip()
                    if not skill_name or len(skill_name) < 2:
                        continue
                    if not SkillFilter.is_valid_skill(skill_name):
                        continue
                    skill_id = f"esco_{self._normalize_id(skill_name)}"
                    if skill_id in self.skills:
                        continue
                    category = self._categorize_skill(skill_name)
                    if not self._is_tech_relevant(skill_name, category):
                        continue
                    aliases = []
                    alt_labels = row.get('altLabels', '')
                    if alt_labels:
                        aliases = [a.strip() for a in alt_labels.split('\n')
                                   if a.strip() and SkillFilter.is_valid_skill(a.strip())]
                    entry = SkillEntry(
                        id=skill_id, name=skill_name, category=category,
                        source='esco', aliases=aliases[:10],
                        description=row.get('description', '')[:200],
                        external_ids={'esco': row.get('conceptUri', '')}
                    )
                    self._add_skill(entry)
                    skills_added += 1
            self._loaded_sources.append(f"ESCO ({skills_added})")
            logger.info(f"Loaded {skills_added} skills from ESCO")
        except Exception as e:
            logger.error(f"Failed to load ESCO: {e}")

    def load_custom(self, file_path: str):
        """Load custom skills from JSON"""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            skills_added = 0
            for skill_data in data.get('skills', []):
                skill_name = skill_data.get('name', '').strip()
                if not skill_name:
                    continue
                skill_id = f"custom_{self._normalize_id(skill_name)}"
                if skill_id in self.skills:
                    continue
                entry = SkillEntry(
                    id=skill_id, name=skill_name,
                    category=skill_data.get('category', 'other'),
                    source='custom',
                    aliases=skill_data.get('aliases', []),
                    keywords=skill_data.get('keywords', [])
                )
                self._add_skill(entry)
                skills_added += 1
            self._loaded_sources.append(f"Custom ({skills_added})")
            logger.info(f"Loaded {skills_added} custom skills")
        except Exception as e:
            logger.error(f"Failed to load custom skills: {e}")

    # ------------------------------------------------------------------
    # LOOKUP
    # ------------------------------------------------------------------

    def find_skill(self, text: str) -> Optional[SkillEntry]:
        """Find a skill by exact name or alias"""
        text_lower = text.lower().strip()
        if text_lower in self.name_index:
            return self.skills[self.name_index[text_lower]]
        if text_lower in self.alias_index:
            return self.skills[self.alias_index[text_lower]]
        return None

    def find_skills_in_text(self, text: str) -> List[SkillEntry]:
        """Extract all taxonomy skills found in text"""
        found = []
        seen = set()
        text_lower = text.lower()
        for skill_id, entry in self.skills.items():
            if self._skill_in_text(entry.name, text_lower):
                if entry.name.lower() not in seen:
                    seen.add(entry.name.lower())
                    found.append(entry)
                continue
            for alias in entry.aliases:
                if self._skill_in_text(alias, text_lower):
                    if entry.name.lower() not in seen:
                        seen.add(entry.name.lower())
                        found.append(entry)
                    break
        return found

    def get_stats(self) -> Dict:
        return {
            "total_skills": len(self.skills),
            "categories": {cat: len(ids) for cat, ids in self.categories.items()},
            "sources": self._loaded_sources,
            "total_aliases": sum(len(s.aliases) for s in self.skills.values())
        }

    # ------------------------------------------------------------------
    # INTERNALS
    # ------------------------------------------------------------------

    def _load_default_skills(self):
        count = 0
        for skill_data in self._default_tech_skills:
            skill_id = f"default_{self._normalize_id(skill_data['name'])}"
            if skill_id in self.skills:
                continue
            entry = SkillEntry(
                id=skill_id, name=skill_data['name'],
                category=skill_data['category'], source='default',
                aliases=skill_data.get('aliases', []),
                keywords=skill_data.get('keywords', [])
            )
            self._add_skill(entry)
            count += 1
        if count:
            self._loaded_sources.append(f"Built-in ({count})")

    def _add_skill(self, entry: SkillEntry):
        self.skills[entry.id] = entry
        self.name_index[entry.name.lower()] = entry.id
        for alias in entry.aliases:
            self.alias_index[alias.lower()] = entry.id
        keywords = entry.keywords + [entry.name.lower()]
        for keyword in keywords:
            kw = keyword.lower()
            if kw not in self.keyword_index:
                self.keyword_index[kw] = set()
            self.keyword_index[kw].add(entry.id)
        if entry.category not in self.categories:
            self.categories[entry.category] = []
        self.categories[entry.category].append(entry.id)

    def _skill_in_text(self, skill_name: str, text_lower: str) -> bool:
        escaped = re.escape(skill_name.lower())
        pattern = r'\b' + escaped + r'\b'
        return bool(re.search(pattern, text_lower))

    def _normalize_id(self, name: str) -> str:
        return re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')[:50]

    def _categorize_skill(self, skill_name: str) -> str:
        name_lower = skill_name.lower()
        if any(x in name_lower for x in ['python', 'java', 'c++', 'javascript', 'sql', 'ruby', 'php', 'golang', 'rust']):
            return 'programming_language'
        elif any(x in name_lower for x in ['tensorflow', 'pytorch', 'keras', 'scikit']):
            return 'ml_framework'
        elif any(x in name_lower for x in ['aws', 'azure', 'google cloud', 'gcp']):
            return 'cloud_platform'
        elif any(x in name_lower for x in ['docker', 'kubernetes', 'jenkins', 'ci/cd', 'terraform']):
            return 'devops'
        elif any(x in name_lower for x in ['machine learning', 'deep learning', 'neural', 'nlp', ' ai ', 'artificial intelligence']):
            return 'ai_ml'
        elif any(x in name_lower for x in ['database', 'mongodb', 'postgresql', 'mysql', 'redis']):
            return 'database'
        else:
            return 'technical'

    def _is_tech_relevant(self, skill_name: str, category: str) -> bool:
        name_lower = skill_name.lower()
        exclude = ['clean', 'mop', 'food', 'cook', 'animal', 'farm',
                    'forklift', 'textile', 'sewing', 'childcare', 'elderly',
                    'driving', 'lifting', 'carry', 'physical labor']
        return not any(kw in name_lower for kw in exclude)

    def _get_default_tech_skills(self) -> List[Dict]:
        return [
            {"name": "Python", "category": "programming_language", "aliases": ["python3", "py"]},
            {"name": "JavaScript", "category": "programming_language", "aliases": ["JS", "ECMAScript"]},
            {"name": "TypeScript", "category": "programming_language", "aliases": ["TS"]},
            {"name": "Java", "category": "programming_language", "aliases": []},
            {"name": "C++", "category": "programming_language", "aliases": ["cpp"]},
            {"name": "C#", "category": "programming_language", "aliases": ["csharp"]},
            {"name": "Go", "category": "programming_language", "aliases": ["Golang"]},
            {"name": "Rust", "category": "programming_language", "aliases": []},
            {"name": "R", "category": "programming_language", "aliases": ["R language"]},
            {"name": "SQL", "category": "programming_language", "aliases": []},
            {"name": "Scala", "category": "programming_language", "aliases": []},
            {"name": "Ruby", "category": "programming_language", "aliases": []},
            {"name": "PHP", "category": "programming_language", "aliases": []},
            {"name": "Swift", "category": "programming_language", "aliases": []},
            {"name": "Kotlin", "category": "programming_language", "aliases": []},
            {"name": "Bash", "category": "programming_language", "aliases": ["Shell"]},
            {"name": "Machine Learning", "category": "ai_ml", "aliases": ["ML"]},
            {"name": "Deep Learning", "category": "ai_ml", "aliases": ["DL"]},
            {"name": "Natural Language Processing", "category": "ai_ml", "aliases": ["NLP"]},
            {"name": "Computer Vision", "category": "ai_ml", "aliases": ["CV"]},
            {"name": "Large Language Models", "category": "ai_ml", "aliases": ["LLM", "LLMs"]},
            {"name": "Generative AI", "category": "ai_ml", "aliases": ["GenAI"]},
            {"name": "RAG", "category": "ai_ml", "aliases": ["Retrieval Augmented Generation"]},
            {"name": "Neural Networks", "category": "ai_ml", "aliases": []},
            {"name": "TensorFlow", "category": "ml_framework", "aliases": ["TF"]},
            {"name": "PyTorch", "category": "ml_framework", "aliases": []},
            {"name": "Keras", "category": "ml_framework", "aliases": []},
            {"name": "scikit-learn", "category": "ml_framework", "aliases": ["sklearn"]},
            {"name": "XGBoost", "category": "ml_framework", "aliases": []},
            {"name": "Hugging Face", "category": "ml_framework", "aliases": ["HuggingFace"]},
            {"name": "LangChain", "category": "ai_tools", "aliases": ["Langchain"]},
            {"name": "LangGraph", "category": "ai_tools", "aliases": []},
            {"name": "LlamaIndex", "category": "ai_tools", "aliases": []},
            {"name": "CrewAI", "category": "ai_tools", "aliases": []},
            {"name": "Pinecone", "category": "vector_database", "aliases": []},
            {"name": "Chroma", "category": "vector_database", "aliases": ["ChromaDB"]},
            {"name": "FAISS", "category": "vector_database", "aliases": []},
            {"name": "Milvus", "category": "vector_database", "aliases": []},
            {"name": "AWS", "category": "cloud_platform", "aliases": ["Amazon Web Services"]},
            {"name": "Azure", "category": "cloud_platform", "aliases": ["Microsoft Azure"]},
            {"name": "Google Cloud", "category": "cloud_platform", "aliases": ["GCP"]},
            {"name": "Docker", "category": "devops", "aliases": []},
            {"name": "Kubernetes", "category": "devops", "aliases": ["K8s"]},
            {"name": "Terraform", "category": "devops", "aliases": []},
            {"name": "Jenkins", "category": "devops", "aliases": []},
            {"name": "CI/CD", "category": "devops", "aliases": ["CICD"]},
            {"name": "MLOps", "category": "devops", "aliases": []},
            {"name": "Airflow", "category": "devops", "aliases": ["Apache Airflow"]},
            {"name": "MLflow", "category": "devops", "aliases": []},
            {"name": "FastAPI", "category": "api_framework", "aliases": ["Fast API"]},
            {"name": "Flask", "category": "api_framework", "aliases": []},
            {"name": "Django", "category": "api_framework", "aliases": []},
            {"name": "REST API", "category": "api_framework", "aliases": ["RESTful"]},
            {"name": "GraphQL", "category": "api_framework", "aliases": []},
            {"name": "Streamlit", "category": "api_framework", "aliases": []},
            {"name": "React", "category": "frontend", "aliases": ["React.js", "ReactJS"]},
            {"name": "Angular", "category": "frontend", "aliases": ["Angular.js"]},
            {"name": "Vue.js", "category": "frontend", "aliases": ["Vue", "VueJS"]},
            {"name": "Node.js", "category": "backend", "aliases": ["NodeJS", "Node"]},
            {"name": "Pandas", "category": "data_engineering", "aliases": []},
            {"name": "NumPy", "category": "data_engineering", "aliases": ["numpy"]},
            {"name": "Apache Spark", "category": "data_engineering", "aliases": ["Spark", "PySpark"]},
            {"name": "Kafka", "category": "data_engineering", "aliases": ["Apache Kafka"]},
            {"name": "dbt", "category": "data_engineering", "aliases": []},
            {"name": "ETL", "category": "data_engineering", "aliases": []},
            {"name": "Apache NiFi", "category": "data_engineering", "aliases": ["NiFi", "NIFI"]},
            {"name": "Data Pipelines", "category": "data_engineering", "aliases": ["Data Pipeline"]},
            {"name": "PostgreSQL", "category": "database", "aliases": ["Postgres"]},
            {"name": "MySQL", "category": "database", "aliases": []},
            {"name": "MongoDB", "category": "database", "aliases": []},
            {"name": "Redis", "category": "database", "aliases": []},
            {"name": "Elasticsearch", "category": "database", "aliases": []},
            {"name": "Neo4j", "category": "database", "aliases": []},
            {"name": "Snowflake", "category": "database", "aliases": []},
            {"name": "BigQuery", "category": "database", "aliases": []},
            {"name": "Tableau", "category": "visualization", "aliases": []},
            {"name": "Power BI", "category": "visualization", "aliases": ["PowerBI"]},
            {"name": "Plotly", "category": "visualization", "aliases": []},
            {"name": "Matplotlib", "category": "visualization", "aliases": []},
            {"name": "Grafana", "category": "visualization", "aliases": []},
            {"name": "OpenCV", "category": "computer_vision", "aliases": ["cv2"]},
            {"name": "Git", "category": "other", "aliases": []},
            {"name": "Linux", "category": "other", "aliases": []},
            {"name": "Problem Solving", "category": "soft_skill", "aliases": []},
            {"name": "Communication", "category": "soft_skill", "aliases": []},
            {"name": "Team Leadership", "category": "soft_skill", "aliases": ["Leadership"]},
            {"name": "Agile", "category": "methodology", "aliases": ["Scrum", "Agile Methodology"]},
        ]
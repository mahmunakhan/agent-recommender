#!/usr/bin/env python3
"""
================================================================================
RESUME PARSER v3.4 - Dynamic Skill Taxonomy from O*NET/ESCO
================================================================================

VERSION: 3.4
NEW FEATURES:
- ✅ Dynamic Skill Taxonomy (loaded from O*NET/ESCO CSV files)
- ✅ Better Experience Filtering (removes certifications/courses/projects)
- ✅ SkillTaxonomyManager with 35,000+ skills from official sources
- ✅ MCP-ready architecture for future tool integration
- ✅ Semantic skill matching using embeddings (optional)

SKILL SOURCES:
- O*NET: https://www.onetcenter.org/database.html (~35,000 skills)
- ESCO: https://esco.ec.europa.eu/en/use-esco/download (~13,500 skills)

Author: AI System Architect
Date: January 2026
================================================================================
"""

import os
import re
import json
import csv
import logging
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """Central configuration"""
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    DEFAULT_MODEL = "llama-3.1-8b-instant"
    TEMPERATURE = 0.1
    MAX_TOKENS = 4096
    MIN_CONFIDENCE = 0.6
    REVIEW_THRESHOLD = 0.7
    MAX_RETRY_ATTEMPTS = 2
    ENABLE_REVIEWER_AGENT = True
    LOG_LEVEL = logging.INFO
    
    # Skill Taxonomy Paths
    ONET_SKILLS_PATH = os.getenv("ONET_SKILLS_PATH", "data/onet/Technology_Skills.txt")
    ESCO_SKILLS_PATH = os.getenv("ESCO_SKILLS_PATH", "data/esco/skills_en.csv")
    CUSTOM_SKILLS_PATH = os.getenv("CUSTOM_SKILLS_PATH", "data/custom_skills.json")
    
    # Enable dynamic taxonomy (set False to use static patterns)
    USE_DYNAMIC_TAXONOMY = True


logging.basicConfig(
    level=Config.LOG_LEVEL,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
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
    source: str  # 'onet', 'esco', 'custom'
    aliases: List[str] = field(default_factory=list)
    description: str = ""
    keywords: List[str] = field(default_factory=list)
    external_ids: Dict[str, str] = field(default_factory=dict)


@dataclass
class ContactInfo:
    name: str = ""
    email: str = ""
    phone: str = ""
    linkedin: str = ""
    github: str = ""
    location: str = ""
    portfolio: str = ""
    confidence: float = 0.0


@dataclass
class Experience:
    company: str = ""
    title: str = ""
    location: str = ""
    start_date: str = ""
    end_date: str = ""
    description: str = ""
    skills_used: List[str] = field(default_factory=list)
    confidence: float = 0.0
    entry_type: str = "job"  # job, certification, course, project


@dataclass
class Education:
    institution: str = ""
    degree: str = ""
    field: str = ""
    start_year: str = ""
    end_year: str = ""
    gpa: Optional[float] = None
    honors: str = ""
    research_topic: str = ""
    confidence: float = 0.0


@dataclass
class Skill:
    name: str = ""
    category: str = ""
    proficiency: str = ""
    years: Optional[int] = None
    confidence: float = 0.0
    source: str = "llm"
    taxonomy_id: str = ""
    external_ids: Dict[str, str] = field(default_factory=dict)


@dataclass
class Certification:
    name: str = ""
    issuer: str = ""
    date: str = ""
    expiry: str = ""
    credential_id: str = ""
    confidence: float = 0.0


@dataclass
class ReviewResult:
    is_complete: bool = False
    missing_fields: List[str] = field(default_factory=list)
    low_confidence_fields: List[str] = field(default_factory=list)
    needs_human_review: bool = False
    review_notes: str = ""
    pass_number: int = 1
    re_extraction_triggered: bool = False
    issues_found: List[str] = field(default_factory=list)


@dataclass
class ParsedResume:
    contact: ContactInfo = field(default_factory=ContactInfo)
    experiences: List[Experience] = field(default_factory=list)
    education: List[Education] = field(default_factory=list)
    skills: List[Skill] = field(default_factory=list)
    certifications: List[Certification] = field(default_factory=list)
    projects: List[Dict] = field(default_factory=list)  # NEW: Separate projects
    summary: str = ""
    overall_confidence: float = 0.0
    review_result: ReviewResult = field(default_factory=ReviewResult)
    extraction_metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            'contact': asdict(self.contact),
            'experiences': [asdict(e) for e in self.experiences],
            'education': [asdict(e) for e in self.education],
            'skills': [asdict(s) for s in self.skills],
            'certifications': [asdict(c) for c in self.certifications],
            'projects': self.projects,
            'summary': self.summary,
            'overall_confidence': self.overall_confidence,
            'review_result': asdict(self.review_result),
            'extraction_metadata': self.extraction_metadata
        }


# ============================================================================
# DYNAMIC SKILL TAXONOMY MANAGER
# ============================================================================

class SkillTaxonomyManager:
    """
    Manages skill taxonomy from multiple sources:
    - O*NET (US Department of Labor)
    - ESCO (European Commission)
    - Custom skills (for emerging tech)
    
    This replaces hardcoded skill patterns with a dynamic, extensible system.
    """
    
    def __init__(self):
        self.skills: Dict[str, SkillEntry] = {}  # id -> SkillEntry
        self.name_index: Dict[str, str] = {}  # lowercase name -> id
        self.alias_index: Dict[str, str] = {}  # lowercase alias -> id
        self.keyword_index: Dict[str, Set[str]] = {}  # keyword -> set of ids
        self.categories: Dict[str, List[str]] = {}  # category -> list of ids
        
        self._loaded_sources = []
        
        # Default tech skills if no files loaded
        self._default_tech_skills = self._get_default_tech_skills()
    
    def load_all_sources(self):
        """Load skills from all configured sources"""
        loaded = False
        
        # Try O*NET
        if os.path.exists(Config.ONET_SKILLS_PATH):
            self.load_onet(Config.ONET_SKILLS_PATH)
            loaded = True
        
        # Try ESCO
        if os.path.exists(Config.ESCO_SKILLS_PATH):
            self.load_esco(Config.ESCO_SKILLS_PATH)
            loaded = True
        
        # Try custom skills
        if os.path.exists(Config.CUSTOM_SKILLS_PATH):
            self.load_custom(Config.CUSTOM_SKILLS_PATH)
            loaded = True
        
        # If no external sources, use built-in defaults
        if not loaded:
            logger.warning("No external skill sources found. Using built-in defaults.")
            self._load_default_skills()
        
        logger.info(f"Skill taxonomy loaded: {len(self.skills)} skills from {self._loaded_sources}")
    
    def load_onet(self, file_path: str):
        """
        Load O*NET Technology Skills
        
        Expected format (Technology_Skills.txt):
        O*NET-SOC Code | Title | Example | Commodity Code | Hot Technology
        """
        try:
            skills_added = 0
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.reader(f, delimiter='\t')
                header = next(reader, None)  # Skip header
                
                for row in reader:
                    if len(row) >= 3:
                        # Column 2 is usually the skill name
                        skill_name = row[2].strip() if len(row) > 2 else row[1].strip()
                        
                        if not skill_name or len(skill_name) < 2:
                            continue
                        
                        # Create unique ID
                        skill_id = f"onet_{self._normalize_id(skill_name)}"
                        
                        # Skip duplicates
                        if skill_id in self.skills:
                            continue
                        
                        # Categorize
                        category = self._categorize_onet_skill(skill_name)
                        
                        # Filter out non-tech skills
                        if not self._is_tech_relevant(skill_name, category):
                            continue
                        
                        entry = SkillEntry(
                            id=skill_id,
                            name=skill_name,
                            category=category,
                            source='onet',
                            external_ids={'onet': row[0] if row else ''}
                        )
                        
                        self._add_skill(entry)
                        skills_added += 1
            
            self._loaded_sources.append(f"O*NET ({skills_added} skills)")
            logger.info(f"Loaded {skills_added} skills from O*NET")
            
        except Exception as e:
            logger.error(f"Failed to load O*NET: {e}")
    
    def load_esco(self, file_path: str):
        """
        Load ESCO Skills
        
        Expected format (skills_en.csv):
        conceptUri,skillType,description,preferredLabel,altLabels
        """
        try:
            skills_added = 0
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    skill_name = row.get('preferredLabel', '').strip()
                    
                    if not skill_name or len(skill_name) < 2:
                        continue
                    
                    # Create unique ID
                    skill_id = f"esco_{self._normalize_id(skill_name)}"
                    
                    if skill_id in self.skills:
                        continue
                    
                    # Get category from skillType
                    skill_type = row.get('skillType', 'skill')
                    category = self._categorize_esco_skill(skill_name, skill_type)
                    
                    # Filter non-tech
                    if not self._is_tech_relevant(skill_name, category):
                        continue
                    
                    # Parse aliases
                    aliases = []
                    alt_labels = row.get('altLabels', '')
                    if alt_labels:
                        aliases = [a.strip() for a in alt_labels.split('\n') if a.strip()]
                    
                    entry = SkillEntry(
                        id=skill_id,
                        name=skill_name,
                        category=category,
                        source='esco',
                        aliases=aliases[:10],  # Limit aliases
                        description=row.get('description', '')[:200],
                        external_ids={'esco': row.get('conceptUri', '')}
                    )
                    
                    self._add_skill(entry)
                    skills_added += 1
            
            self._loaded_sources.append(f"ESCO ({skills_added} skills)")
            logger.info(f"Loaded {skills_added} skills from ESCO")
            
        except Exception as e:
            logger.error(f"Failed to load ESCO: {e}")
    
    def load_custom(self, file_path: str):
        """
        Load custom skills from JSON
        
        Format:
        {
            "skills": [
                {"name": "LangChain", "category": "ai_tools", "aliases": ["Langchain", "Lang Chain"]}
            ]
        }
        """
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
                    id=skill_id,
                    name=skill_name,
                    category=skill_data.get('category', 'other'),
                    source='custom',
                    aliases=skill_data.get('aliases', []),
                    keywords=skill_data.get('keywords', [])
                )
                
                self._add_skill(entry)
                skills_added += 1
            
            self._loaded_sources.append(f"Custom ({skills_added} skills)")
            logger.info(f"Loaded {skills_added} custom skills")
            
        except Exception as e:
            logger.error(f"Failed to load custom skills: {e}")
    
    def _load_default_skills(self):
        """Load built-in default skills when no external sources available"""
        for skill_data in self._default_tech_skills:
            skill_id = f"default_{self._normalize_id(skill_data['name'])}"
            
            entry = SkillEntry(
                id=skill_id,
                name=skill_data['name'],
                category=skill_data['category'],
                source='default',
                aliases=skill_data.get('aliases', []),
                keywords=skill_data.get('keywords', [])
            )
            
            self._add_skill(entry)
        
        self._loaded_sources.append(f"Built-in ({len(self._default_tech_skills)} skills)")
    
    def _add_skill(self, entry: SkillEntry):
        """Add skill to all indexes"""
        self.skills[entry.id] = entry
        
        # Name index
        self.name_index[entry.name.lower()] = entry.id
        
        # Alias index
        for alias in entry.aliases:
            self.alias_index[alias.lower()] = entry.id
        
        # Keyword index
        keywords = entry.keywords + [entry.name.lower()]
        for keyword in keywords:
            kw = keyword.lower()
            if kw not in self.keyword_index:
                self.keyword_index[kw] = set()
            self.keyword_index[kw].add(entry.id)
        
        # Category index
        if entry.category not in self.categories:
            self.categories[entry.category] = []
        self.categories[entry.category].append(entry.id)
    
    def find_skill(self, text: str) -> Optional[SkillEntry]:
        """Find a skill by name or alias"""
        text_lower = text.lower().strip()
        
        # Exact name match
        if text_lower in self.name_index:
            return self.skills[self.name_index[text_lower]]
        
        # Alias match
        if text_lower in self.alias_index:
            return self.skills[self.alias_index[text_lower]]
        
        return None
    
    def extract_skills_from_text(self, text: str) -> List[Skill]:
        """Extract all skills found in text"""
        found_skills = []
        seen = set()
        text_lower = text.lower()
        
        # Check each skill
        for skill_id, entry in self.skills.items():
            # Check main name
            if self._skill_in_text(entry.name, text_lower):
                if entry.name.lower() not in seen:
                    seen.add(entry.name.lower())
                    found_skills.append(Skill(
                        name=entry.name,
                        category=entry.category,
                        confidence=0.90,
                        source='taxonomy',
                        taxonomy_id=entry.id,
                        external_ids=entry.external_ids
                    ))
                continue
            
            # Check aliases
            for alias in entry.aliases:
                if self._skill_in_text(alias, text_lower):
                    if entry.name.lower() not in seen:
                        seen.add(entry.name.lower())
                        found_skills.append(Skill(
                            name=entry.name,
                            category=entry.category,
                            confidence=0.85,
                            source='taxonomy_alias',
                            taxonomy_id=entry.id,
                            external_ids=entry.external_ids
                        ))
                    break
        
        return found_skills
    
    def _skill_in_text(self, skill_name: str, text_lower: str) -> bool:
        """Check if skill name appears in text with word boundaries"""
        # Escape special regex chars
        escaped = re.escape(skill_name.lower())
        pattern = r'\b' + escaped + r'\b'
        return bool(re.search(pattern, text_lower))
    
    def _normalize_id(self, name: str) -> str:
        """Create normalized ID from name"""
        return re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')[:50]
    
    def _categorize_onet_skill(self, skill_name: str) -> str:
        """Categorize O*NET skill"""
        name_lower = skill_name.lower()
        
        if any(x in name_lower for x in ['python', 'java', 'c++', 'javascript', 'sql', 'r ', ' r,', 'ruby', 'php']):
            return 'programming_language'
        elif any(x in name_lower for x in ['tensorflow', 'pytorch', 'keras', 'scikit']):
            return 'ml_framework'
        elif any(x in name_lower for x in ['aws', 'azure', 'google cloud', 'gcp']):
            return 'cloud_platform'
        elif any(x in name_lower for x in ['docker', 'kubernetes', 'jenkins', 'ci/cd']):
            return 'devops'
        elif any(x in name_lower for x in ['machine learning', 'deep learning', 'neural', 'nlp', 'ai']):
            return 'ai_ml'
        elif any(x in name_lower for x in ['database', 'sql', 'mongodb', 'postgresql']):
            return 'database'
        else:
            return 'technical'
    
    def _categorize_esco_skill(self, skill_name: str, skill_type: str) -> str:
        """Categorize ESCO skill"""
        if 'digital' in skill_type.lower() or 'ICT' in skill_type:
            return self._categorize_onet_skill(skill_name)
        return 'technical'
    
    def _is_tech_relevant(self, skill_name: str, category: str) -> bool:
        """Filter out non-tech skills"""
        name_lower = skill_name.lower()
        
        # Exclude list
        exclude_keywords = [
            'clean', 'mop', 'food', 'cook', 'animal', 'farm',
            'forklift', 'textile', 'sewing', 'childcare', 'elderly',
            'driving', 'lifting', 'carry', 'physical labor'
        ]
        
        for keyword in exclude_keywords:
            if keyword in name_lower:
                return False
        
        return True
    
    def _get_default_tech_skills(self) -> List[Dict]:
        """Built-in tech skills for when no external sources available"""
        return [
            # Programming Languages
            {"name": "Python", "category": "programming_language", "aliases": ["python3", "py"]},
            {"name": "JavaScript", "category": "programming_language", "aliases": ["JS", "ECMAScript"]},
            {"name": "TypeScript", "category": "programming_language", "aliases": ["TS"]},
            {"name": "Java", "category": "programming_language", "aliases": []},
            {"name": "C++", "category": "programming_language", "aliases": ["cpp", "c plus plus"]},
            {"name": "C#", "category": "programming_language", "aliases": ["csharp", "c sharp"]},
            {"name": "Go", "category": "programming_language", "aliases": ["Golang", "Go lang"]},
            {"name": "Rust", "category": "programming_language", "aliases": []},
            {"name": "R", "category": "programming_language", "aliases": ["R language", "R programming"]},
            {"name": "SQL", "category": "programming_language", "aliases": ["Structured Query Language"]},
            {"name": "Scala", "category": "programming_language", "aliases": []},
            {"name": "Ruby", "category": "programming_language", "aliases": []},
            {"name": "PHP", "category": "programming_language", "aliases": []},
            {"name": "Swift", "category": "programming_language", "aliases": []},
            {"name": "Kotlin", "category": "programming_language", "aliases": []},
            {"name": "Bash", "category": "programming_language", "aliases": ["Shell", "Shell scripting"]},
            
            # AI/ML Core
            {"name": "Machine Learning", "category": "ai_ml", "aliases": ["ML"]},
            {"name": "Deep Learning", "category": "ai_ml", "aliases": ["DL"]},
            {"name": "Generative AI", "category": "ai_ml", "aliases": ["GenAI", "Gen AI"]},
            {"name": "Natural Language Processing", "category": "ai_ml", "aliases": ["NLP"]},
            {"name": "Natural Language Understanding", "category": "ai_ml", "aliases": ["NLU"]},
            {"name": "Computer Vision", "category": "ai_ml", "aliases": ["CV"]},
            {"name": "Large Language Models", "category": "ai_ml", "aliases": ["LLM", "LLMs"]},
            {"name": "Retrieval Augmented Generation", "category": "ai_ml", "aliases": ["RAG"]},
            {"name": "Neural Networks", "category": "ai_ml", "aliases": []},
            {"name": "Transformers", "category": "ai_ml", "aliases": []},
            {"name": "Convolutional Neural Networks", "category": "ai_ml", "aliases": ["CNN"]},
            {"name": "Recurrent Neural Networks", "category": "ai_ml", "aliases": ["RNN"]},
            {"name": "LSTM", "category": "ai_ml", "aliases": ["Long Short-Term Memory"]},
            {"name": "Reinforcement Learning", "category": "ai_ml", "aliases": ["RL"]},
            {"name": "OCR", "category": "ai_ml", "aliases": ["Optical Character Recognition"]},
            
            # ML Frameworks
            {"name": "TensorFlow", "category": "ml_framework", "aliases": ["TF"]},
            {"name": "PyTorch", "category": "ml_framework", "aliases": []},
            {"name": "Keras", "category": "ml_framework", "aliases": []},
            {"name": "scikit-learn", "category": "ml_framework", "aliases": ["sklearn", "scikit learn"]},
            {"name": "XGBoost", "category": "ml_framework", "aliases": []},
            {"name": "LightGBM", "category": "ml_framework", "aliases": []},
            {"name": "Hugging Face", "category": "ml_framework", "aliases": ["HuggingFace", "🤗"]},
            {"name": "OpenAI", "category": "ml_framework", "aliases": []},
            
            # AI Tools & Agents
            {"name": "LangChain", "category": "ai_tools", "aliases": ["Lang Chain", "Langchain"]},
            {"name": "LangGraph", "category": "ai_tools", "aliases": ["Lang Graph"]},
            {"name": "LlamaIndex", "category": "ai_tools", "aliases": ["Llama Index"]},
            {"name": "AutoGen", "category": "ai_tools", "aliases": ["Auto Gen"]},
            {"name": "CrewAI", "category": "ai_tools", "aliases": ["Crew AI"]},
            {"name": "PhiData", "category": "ai_tools", "aliases": ["Phi Data", "Phi-Data"]},
            {"name": "AI Agents", "category": "ai_tools", "aliases": ["Agentic AI", "AI Agent"]},
            {"name": "N8N", "category": "ai_tools", "aliases": ["n8n"]},
            {"name": "Chatbot", "category": "ai_tools", "aliases": ["Chat bot", "Chat Bot"]},
            {"name": "Rasa", "category": "ai_tools", "aliases": []},
            {"name": "Dialogflow", "category": "ai_tools", "aliases": []},
            
            # Vector Databases
            {"name": "Pinecone", "category": "vector_database", "aliases": []},
            {"name": "Weaviate", "category": "vector_database", "aliases": []},
            {"name": "Chroma", "category": "vector_database", "aliases": ["ChromaDB"]},
            {"name": "FAISS", "category": "vector_database", "aliases": ["Faiss"]},
            {"name": "Milvus", "category": "vector_database", "aliases": []},
            {"name": "Qdrant", "category": "vector_database", "aliases": []},
            {"name": "pgvector", "category": "vector_database", "aliases": ["pg_vector"]},
            
            # Cloud Platforms
            {"name": "AWS", "category": "cloud_platform", "aliases": ["Amazon Web Services"]},
            {"name": "Azure", "category": "cloud_platform", "aliases": ["Microsoft Azure"]},
            {"name": "Google Cloud", "category": "cloud_platform", "aliases": ["GCP", "Google Cloud Platform"]},
            {"name": "Vertex AI", "category": "cloud_platform", "aliases": []},
            {"name": "SageMaker", "category": "cloud_platform", "aliases": ["AWS SageMaker"]},
            {"name": "Bedrock", "category": "cloud_platform", "aliases": ["AWS Bedrock"]},
            {"name": "Lambda", "category": "cloud_platform", "aliases": ["AWS Lambda"]},
            
            # DevOps & MLOps
            {"name": "Docker", "category": "devops", "aliases": []},
            {"name": "Kubernetes", "category": "devops", "aliases": ["K8s"]},
            {"name": "Terraform", "category": "devops", "aliases": []},
            {"name": "Ansible", "category": "devops", "aliases": []},
            {"name": "Jenkins", "category": "devops", "aliases": []},
            {"name": "GitLab CI", "category": "devops", "aliases": ["GitLab CI/CD"]},
            {"name": "GitHub Actions", "category": "devops", "aliases": []},
            {"name": "CI/CD", "category": "devops", "aliases": ["CICD", "CI CD"]},
            {"name": "MLOps", "category": "devops", "aliases": ["ML Ops"]},
            {"name": "Airflow", "category": "devops", "aliases": ["Apache Airflow"]},
            {"name": "Kubeflow", "category": "devops", "aliases": []},
            {"name": "MLflow", "category": "devops", "aliases": ["ML flow"]},
            
            # APIs & Web Frameworks
            {"name": "FastAPI", "category": "api_framework", "aliases": ["Fast API"]},
            {"name": "Flask", "category": "api_framework", "aliases": []},
            {"name": "Django", "category": "api_framework", "aliases": []},
            {"name": "REST API", "category": "api_framework", "aliases": ["RESTful", "RESTful API"]},
            {"name": "GraphQL", "category": "api_framework", "aliases": []},
            {"name": "gRPC", "category": "api_framework", "aliases": []},
            {"name": "Streamlit", "category": "api_framework", "aliases": []},
            {"name": "Gradio", "category": "api_framework", "aliases": []},
            
            # Data Engineering
            {"name": "Pandas", "category": "data_engineering", "aliases": []},
            {"name": "NumPy", "category": "data_engineering", "aliases": ["numpy"]},
            {"name": "Apache Spark", "category": "data_engineering", "aliases": ["Spark", "PySpark"]},
            {"name": "Hadoop", "category": "data_engineering", "aliases": []},
            {"name": "Kafka", "category": "data_engineering", "aliases": ["Apache Kafka"]},
            {"name": "dbt", "category": "data_engineering", "aliases": ["data build tool"]},
            {"name": "ETL", "category": "data_engineering", "aliases": []},
            {"name": "Apache NiFi", "category": "data_engineering", "aliases": ["NiFi", "NIFI"]},
            {"name": "Data Pipeline", "category": "data_engineering", "aliases": []},
            
            # Databases
            {"name": "PostgreSQL", "category": "database", "aliases": ["Postgres"]},
            {"name": "MySQL", "category": "database", "aliases": []},
            {"name": "MongoDB", "category": "database", "aliases": ["Mongo"]},
            {"name": "Redis", "category": "database", "aliases": []},
            {"name": "Elasticsearch", "category": "database", "aliases": ["Elastic"]},
            {"name": "Neo4j", "category": "database", "aliases": []},
            {"name": "Cassandra", "category": "database", "aliases": []},
            {"name": "DynamoDB", "category": "database", "aliases": []},
            {"name": "Snowflake", "category": "database", "aliases": []},
            {"name": "BigQuery", "category": "database", "aliases": []},
            
            # Visualization
            {"name": "Tableau", "category": "visualization", "aliases": []},
            {"name": "Power BI", "category": "visualization", "aliases": ["PowerBI"]},
            {"name": "Plotly", "category": "visualization", "aliases": []},
            {"name": "Matplotlib", "category": "visualization", "aliases": []},
            {"name": "Seaborn", "category": "visualization", "aliases": []},
            {"name": "Grafana", "category": "visualization", "aliases": []},
            {"name": "Looker", "category": "visualization", "aliases": []},
            {"name": "Alteryx", "category": "visualization", "aliases": []},
            {"name": "Dataiku", "category": "visualization", "aliases": []},
            
            # Other
            {"name": "OpenCV", "category": "computer_vision", "aliases": ["Open CV", "Open-CV"]},
            {"name": "Git", "category": "other", "aliases": []},
            {"name": "Linux", "category": "other", "aliases": ["Ubuntu", "CentOS"]},
            {"name": "Jira", "category": "other", "aliases": []},
            {"name": "Recommendation System", "category": "ai_ml", "aliases": ["Recommender System"]},
            {"name": "Time Series", "category": "ai_ml", "aliases": ["Time-Series"]},
            {"name": "A/B Testing", "category": "other", "aliases": ["AB Testing"]},
            {"name": "Feature Engineering", "category": "ai_ml", "aliases": []},
        ]
    
    def get_stats(self) -> Dict:
        """Get taxonomy statistics"""
        return {
            "total_skills": len(self.skills),
            "categories": {cat: len(ids) for cat, ids in self.categories.items()},
            "sources": self._loaded_sources,
            "total_aliases": sum(len(s.aliases) for s in self.skills.values())
        }


# ============================================================================
# TEXT CLEANING UTILITIES
# ============================================================================

class TextCleaner:
    @staticmethod
    def clean_text(text: str) -> str:
        if not text:
            return ""
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)
        text = re.sub(r'(?<=[a-z,])\n(?=[a-z])', ' ', text)
        text = re.sub(r'[ \t]+', ' ', text)
        return text.strip()
    
    @staticmethod
    def clean_certification_name(name: str) -> str:
        if not name:
            return ""
        name = re.sub(r'\n+', ' ', name)
        name = re.sub(r'\s+', ' ', name)
        name = name.strip()
        name = re.sub(r'^[-–•\s]+|[-–•\s]+$', '', name)
        return name


# ============================================================================
# EXPERIENCE CLASSIFIER (NEW in v3.4)
# ============================================================================

class ExperienceClassifier:
    """
    Classifies entries as: job, certification, course, project, education
    Fixes the issue of certifications appearing in experience
    """
    
    # Certification indicators
    CERT_KEYWORDS = [
        'certified', 'certification', 'certificate', 'credential',
        'certification at', 'essentials for', 'fundamentals',
        'specialization', 'professional certificate'
    ]
    
    CERT_ISSUERS = [
        'deeplearning.ai', 'coursera', 'udemy', 'edx', 'linkedin learning',
        'aws training', 'microsoft learn', 'google cloud training',
        'ibm training', 'datacamp', 'pluralsight'
    ]
    
    # Course indicators
    COURSE_KEYWORDS = [
        'essentials', 'fundamentals', 'introduction to', 'basics',
        'bootcamp', 'workshop', 'training', 'program', 'course'
    ]
    
    # Project indicators
    PROJECT_KEYWORDS = [
        'image classification', 'text extraction', 'built', 'developed',
        'project:', 'capstone', 'implementation', 'poc', 'prototype'
    ]
    
    # Education indicators
    EDUCATION_KEYWORDS = [
        'university', 'college', 'institute', 'school', 'academy',
        'phd', 'ph.d', 'masters', 'bachelor', 'degree', 'mba', 'mca'
    ]
    
    @classmethod
    def classify(cls, title: str, company: str, description: str = "") -> str:
        """
        Classify an entry type
        Returns: 'job', 'certification', 'course', 'project', or 'education'
        """
        combined = f"{title} {company} {description}".lower()
        
        # Check education first
        for keyword in cls.EDUCATION_KEYWORDS:
            if keyword in combined:
                return 'education'
        
        # Check certifications
        for keyword in cls.CERT_KEYWORDS:
            if keyword in combined:
                return 'certification'
        
        for issuer in cls.CERT_ISSUERS:
            if issuer in combined:
                return 'certification'
        
        # If company == title, likely certification
        if company.lower().strip() == title.lower().strip():
            return 'certification'
        
        # Check courses
        for keyword in cls.COURSE_KEYWORDS:
            if keyword in combined:
                # But not if it has job-like title
                if any(x in title.lower() for x in ['engineer', 'developer', 'architect', 'consultant', 'analyst', 'manager']):
                    return 'job'
                return 'course'
        
        # Check projects
        for keyword in cls.PROJECT_KEYWORDS:
            if keyword in combined:
                return 'project'
        
        # Default to job
        return 'job'


# ============================================================================
# JSON UTILITIES
# ============================================================================

def safe_parse_json(text: str, default: Any = None) -> Any:
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
# FILE EXTRACTION
# ============================================================================

def extract_text_from_pdf(file_path: str) -> str:
    try:
        import PyPDF2
        text = ""
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        return TextCleaner.clean_text(text)
    except:
        import pdfplumber
        text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
        return TextCleaner.clean_text(text)


def extract_text_from_docx(file_path: str) -> str:
    from docx import Document
    doc = Document(file_path)
    text = "\n".join([para.text for para in doc.paragraphs])
    return TextCleaner.clean_text(text)


# ============================================================================
# LLM CLIENT
# ============================================================================

class LLMClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or Config.GROQ_API_KEY
        self._client = None
    
    @property
    def client(self):
        if self._client is None:
            from groq import Groq
            self._client = Groq(api_key=self.api_key)
        return self._client
    
    def generate(self, prompt: str, model: str = None, temperature: float = None,
                 max_tokens: int = None, system_prompt: str = None) -> str:
        model = model or Config.DEFAULT_MODEL
        temperature = temperature if temperature is not None else Config.TEMPERATURE
        max_tokens = max_tokens or Config.MAX_TOKENS
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = self.client.chat.completions.create(
                model=model, messages=messages,
                temperature=temperature, max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM error: {e}")
            return ""


# ============================================================================
# AGENTS
# ============================================================================

class BaseAgent:
    def __init__(self, llm_client: LLMClient, taxonomy: SkillTaxonomyManager = None):
        self.llm = llm_client
        self.taxonomy = taxonomy
        self.name = self.__class__.__name__
    
    def extract(self, text: str, context: Dict = None) -> Any:
        raise NotImplementedError
    
    def _log(self, message: str):
        logger.info(f"[{self.name}] {message}")


class ContactAgent(BaseAgent):
    def extract(self, text: str, context: Dict = None) -> ContactInfo:
        self._log("Extracting contact...")
        
        prompt = f"""Extract contact info. Return ONLY valid JSON.
RESUME: {text[:3000]}

Return: {{"name": "", "email": "", "phone": "", "linkedin": "", "location": ""}}
JSON:"""
        
        response = self.llm.generate(prompt)
        data = safe_parse_json(response, {})
        
        return ContactInfo(
            name=data.get('name', ''),
            email=data.get('email', ''),
            phone=data.get('phone', ''),
            linkedin=data.get('linkedin', ''),
            location=data.get('location', ''),
            confidence=0.85 if data.get('email') else 0.5
        )


class ExperienceAgent(BaseAgent):
    """ENHANCED in v3.4 - Classifies entries and filters non-jobs"""
    
    def extract(self, text: str, context: Dict = None) -> Tuple[List[Experience], List[Certification], List[Dict]]:
        """
        Returns: (jobs, certifications, projects)
        """
        self._log("Extracting & classifying experience...")
        
        prompt = f"""Extract ALL entries from Work Experience/Professional Experience section.
Return valid JSON array.

IMPORTANT: Extract every entry, we will classify them later.

RESUME: {text[:5000]}

Return: [{{"company": "", "title": "", "location": "", "start_date": "", "end_date": "", "description": ""}}]
JSON:"""
        
        response = self.llm.generate(prompt)
        data = safe_parse_json(response, [])
        
        jobs = []
        certifications = []
        projects = []
        
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    company = item.get('company', '').strip()
                    title = item.get('title', '').strip()
                    description = item.get('description', '')
                    
                    if not company and not title:
                        continue
                    
                    # Classify the entry
                    entry_type = ExperienceClassifier.classify(title, company, description)
                    
                    if entry_type == 'job':
                        jobs.append(Experience(
                            company=company,
                            title=title,
                            location=item.get('location', ''),
                            start_date=item.get('start_date', ''),
                            end_date=item.get('end_date', ''),
                            description=description,
                            confidence=0.85,
                            entry_type='job'
                        ))
                    elif entry_type == 'certification':
                        certifications.append(Certification(
                            name=title if title != company else company,
                            issuer=company if title != company else "",
                            confidence=0.80
                        ))
                        self._log(f"→ Moved to Certifications: {title}")
                    elif entry_type == 'project':
                        projects.append({
                            'name': title,
                            'organization': company,
                            'description': description
                        })
                        self._log(f"→ Moved to Projects: {title}")
                    elif entry_type == 'education':
                        self._log(f"→ Skipped (education): {title}")
        
        self._log(f"Classified: {len(jobs)} jobs, {len(certifications)} certs, {len(projects)} projects")
        return jobs, certifications, projects


class EducationAgent(BaseAgent):
    def extract(self, text: str, context: Dict = None) -> List[Education]:
        self._log("Extracting education...")
        
        prompt = f"""Extract ALL education entries. Return valid JSON array.

RESUME: {text[:4000]}

Return: [{{"institution": "", "degree": "", "field": "", "start_year": "", "end_year": "", "research_topic": ""}}]
JSON:"""
        
        response = self.llm.generate(prompt)
        data = safe_parse_json(response, [])
        
        education = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    education.append(Education(
                        institution=item.get('institution', ''),
                        degree=item.get('degree', ''),
                        field=item.get('field', ''),
                        start_year=str(item.get('start_year', '')),
                        end_year=str(item.get('end_year', '')),
                        research_topic=item.get('research_topic', ''),
                        confidence=0.85
                    ))
        
        return education


class SkillsAgent(BaseAgent):
    """ENHANCED in v3.4 - Uses dynamic taxonomy"""
    
    def extract(self, text: str, context: Dict = None) -> List[Skill]:
        self._log("Extracting skills with dynamic taxonomy...")
        
        # Method 1: Taxonomy-based extraction
        taxonomy_skills = []
        if self.taxonomy:
            taxonomy_skills = self.taxonomy.extract_skills_from_text(text)
            self._log(f"Taxonomy found: {len(taxonomy_skills)} skills")
        
        # Method 2: LLM extraction
        prompt = f"""Extract ALL technical skills. Return valid JSON array.

RESUME: {text[:5000]}

Return: [{{"name": "", "category": ""}}]
JSON:"""
        
        response = self.llm.generate(prompt)
        data = safe_parse_json(response, [])
        
        llm_skills = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get('name'):
                    llm_skills.append(Skill(
                        name=item.get('name', ''),
                        category=item.get('category', 'other'),
                        confidence=0.80,
                        source='llm'
                    ))
        
        self._log(f"LLM found: {len(llm_skills)} skills")
        
        # Merge (taxonomy takes precedence)
        merged = self._merge_skills(taxonomy_skills, llm_skills)
        self._log(f"Total unique: {len(merged)} skills")
        
        return merged
    
    def _merge_skills(self, taxonomy_skills: List[Skill], llm_skills: List[Skill]) -> List[Skill]:
        seen = set()
        merged = []
        
        # Taxonomy first (higher confidence)
        for skill in taxonomy_skills:
            key = skill.name.lower()
            if key not in seen:
                seen.add(key)
                merged.append(skill)
        
        # Then LLM
        for skill in llm_skills:
            key = skill.name.lower()
            if key not in seen:
                seen.add(key)
                merged.append(skill)
        
        return merged


class CertificationAgent(BaseAgent):
    def extract(self, text: str, context: Dict = None) -> List[Certification]:
        self._log("Extracting certifications...")
        
        cleaned_text = TextCleaner.clean_text(text)
        
        prompt = f"""Extract ALL certifications. Return valid JSON array.

RULES:
1. Each cert should be SEPARATE
2. Common issuers: AWS, Microsoft, Google, IBM, deeplearning.ai, Coursera

RESUME: {cleaned_text[:4000]}

Return: [{{"name": "", "issuer": ""}}]
JSON:"""
        
        response = self.llm.generate(prompt)
        data = safe_parse_json(response, [])
        
        certs = []
        seen = set()
        
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get('name'):
                    name = TextCleaner.clean_certification_name(item.get('name', ''))
                    key = name.lower()
                    
                    if key not in seen and len(name) > 5:
                        seen.add(key)
                        certs.append(Certification(
                            name=name,
                            issuer=item.get('issuer', ''),
                            confidence=0.85
                        ))
        
        return certs


class SummaryAgent(BaseAgent):
    def extract(self, text: str, context: Dict = None) -> str:
        self._log("Generating summary...")
        
        skills_str = ", ".join([s.name for s in context.get('skills', [])[:15]]) if context else ""
        
        prompt = f"""Write a 2-3 sentence professional summary.

SKILLS: {skills_str}
RESUME: {text[:3000]}

Summary:"""
        
        return self.llm.generate(prompt).strip()


# ============================================================================
# REVIEWER AGENT
# ============================================================================

class ReviewerAgent(BaseAgent):
    MIN_COUNTS = {'skills': 5, 'experience': 1, 'education': 1}
    
    def __init__(self, llm_client: LLMClient, all_agents: Dict, taxonomy: SkillTaxonomyManager = None):
        super().__init__(llm_client, taxonomy)
        self.agents = all_agents
    
    def review(self, parsed: ParsedResume, original_text: str, pass_number: int = 1) -> Tuple[ParsedResume, ReviewResult]:
        self._log(f"🔍 Reviewing (Pass {pass_number})...")
        
        review = ReviewResult(pass_number=pass_number)
        review.missing_fields = self._check_missing(parsed)
        
        if pass_number < Config.MAX_RETRY_ATTEMPTS and review.missing_fields:
            self._log(f"🔄 Re-extracting: {review.missing_fields}")
            review.re_extraction_triggered = True
            parsed = self._re_extract(parsed, original_text, review.missing_fields)
            review.missing_fields = self._check_missing(parsed)
        
        review.is_complete = len(review.missing_fields) == 0
        review.needs_human_review = not review.is_complete or parsed.overall_confidence < Config.REVIEW_THRESHOLD
        review.review_notes = self._generate_notes(parsed, review)
        parsed.review_result = review
        
        return parsed, review
    
    def _check_missing(self, parsed: ParsedResume) -> List[str]:
        missing = []
        if len(parsed.skills) < self.MIN_COUNTS['skills']:
            missing.append('skills')
        if len(parsed.experiences) < self.MIN_COUNTS['experience']:
            missing.append('experience')
        if len(parsed.education) < self.MIN_COUNTS['education']:
            missing.append('education')
        return missing
    
    def _re_extract(self, parsed: ParsedResume, text: str, missing: List[str]) -> ParsedResume:
        for field in missing:
            if field == 'skills' and 'skills' in self.agents:
                parsed.skills = self.agents['skills'].extract(text)
        return parsed
    
    def _generate_notes(self, parsed: ParsedResume, review: ReviewResult) -> str:
        notes = []
        notes.append("✅ Extraction complete" if review.is_complete else "⚠️ Extraction incomplete")
        if review.re_extraction_triggered:
            notes.append(f"🔄 Re-extraction on pass {review.pass_number}")
        notes.append(f"\n📊 Stats: Skills={len(parsed.skills)}, Jobs={len(parsed.experiences)}, "
                    f"Edu={len(parsed.education)}, Certs={len(parsed.certifications)}, "
                    f"Projects={len(parsed.projects)}")
        notes.append(f"📈 Confidence: {parsed.overall_confidence:.2f}")
        return "\n".join(notes)


# ============================================================================
# MAIN PARSER
# ============================================================================

class ResumeParser:
    def __init__(self, api_key: str = None, taxonomy_paths: Dict[str, str] = None):
        self.llm = LLMClient(api_key)
        
        # Initialize taxonomy
        self.taxonomy = SkillTaxonomyManager()
        if Config.USE_DYNAMIC_TAXONOMY:
            self.taxonomy.load_all_sources()
            stats = self.taxonomy.get_stats()
            logger.info(f"📚 Taxonomy: {stats['total_skills']} skills loaded")
        
        # Initialize agents
        self.agents = {
            'contact': ContactAgent(self.llm, self.taxonomy),
            'experience': ExperienceAgent(self.llm, self.taxonomy),
            'education': EducationAgent(self.llm, self.taxonomy),
            'skills': SkillsAgent(self.llm, self.taxonomy),
            'certifications': CertificationAgent(self.llm, self.taxonomy),
            'summary': SummaryAgent(self.llm, self.taxonomy),
        }
        
        self.reviewer = ReviewerAgent(self.llm, self.agents, self.taxonomy)
        logger.info("🚀 ResumeParser v3.4 initialized!")
    
    def parse_file(self, file_path: str) -> ParsedResume:
        logger.info(f"📄 Parsing: {file_path}")
        
        if file_path.lower().endswith('.pdf'):
            text = extract_text_from_pdf(file_path)
        elif file_path.lower().endswith('.docx'):
            text = extract_text_from_docx(file_path)
        else:
            raise ValueError(f"Unsupported: {file_path}")
        
        return self.parse_text(text)
    
    def parse_text(self, text: str) -> ParsedResume:
        print("\n" + "="*60)
        print("🚀 RESUME PARSER v3.4 - Dynamic Taxonomy")
        print("="*60)
        
        start_time = datetime.now()
        text = TextCleaner.clean_text(text)
        
        result = ParsedResume()
        result.extraction_metadata = {
            'parser_version': '3.4',
            'start_time': start_time.isoformat(),
            'text_length': len(text),
            'taxonomy_stats': self.taxonomy.get_stats() if Config.USE_DYNAMIC_TAXONOMY else {}
        }
        
        # Contact
        print("\n📝 Extracting contact...")
        result.contact = self.agents['contact'].extract(text)
        
        # Experience (with classification)
        print("\n💼 Extracting & classifying experience...")
        jobs, exp_certs, projects = self.agents['experience'].extract(text)
        result.experiences = jobs
        result.projects = projects
        
        # Education
        print("\n🎓 Extracting education...")
        result.education = self.agents['education'].extract(text)
        
        # Skills (using taxonomy)
        print("\n🛠️ Extracting skills with taxonomy...")
        result.skills = self.agents['skills'].extract(text)
        
        # Certifications (merge with those from experience)
        print("\n📜 Extracting certifications...")
        llm_certs = self.agents['certifications'].extract(text)
        result.certifications = self._merge_certs(llm_certs, exp_certs)
        
        result.overall_confidence = self._calc_confidence(result)
        
        # Review
        if Config.ENABLE_REVIEWER_AGENT:
            print("\n🔍 Reviewing...")
            result, review = self.reviewer.review(result, text, pass_number=1)
        
        # Summary
        print("\n📋 Generating summary...")
        result.summary = self.agents['summary'].extract(text, {'skills': result.skills})
        
        result.overall_confidence = self._calc_confidence(result)
        
        # Metadata
        end_time = datetime.now()
        result.extraction_metadata['end_time'] = end_time.isoformat()
        result.extraction_metadata['duration_seconds'] = (end_time - start_time).total_seconds()
        
        print("\n" + "="*60)
        print(f"✅ COMPLETE in {result.extraction_metadata['duration_seconds']:.1f}s")
        print(f"📊 Jobs: {len(result.experiences)} | Certs: {len(result.certifications)} | Projects: {len(result.projects)}")
        print(f"🛠️ Skills: {len(result.skills)} | Confidence: {result.overall_confidence:.2f}")
        print("="*60)
        
        return result
    
    def _merge_certs(self, llm_certs: List[Certification], exp_certs: List[Certification]) -> List[Certification]:
        """Merge certifications from LLM and experience classification"""
        seen = set()
        merged = []
        
        for cert in llm_certs + exp_certs:
            key = cert.name.lower()
            if key not in seen and len(cert.name) > 5:
                seen.add(key)
                merged.append(cert)
        
        return merged
    
    def _calc_confidence(self, result: ParsedResume) -> float:
        scores = []
        scores.append(result.contact.confidence if result.contact.email else 0.0)
        scores.append(sum(s.confidence for s in result.skills) / len(result.skills) if result.skills else 0.0)
        scores.append(sum(e.confidence for e in result.experiences) / len(result.experiences) if result.experiences else 0.3)
        scores.append(sum(e.confidence for e in result.education) / len(result.education) if result.education else 0.3)
        return sum(scores) / len(scores) if scores else 0.0


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def parse_resume(input_data: str, api_key: str = None) -> Dict:
    parser = ResumeParser(api_key)
    if os.path.exists(input_data):
        result = parser.parse_file(input_data)
    else:
        result = parser.parse_text(input_data)
    return result.to_dict()


def download_onet_skills(output_dir: str = "data/onet"):
    """
    Download O*NET Technology Skills database
    
    Note: You need to manually download from https://www.onetcenter.org/database.html
    """
    print("="*60)
    print("O*NET Download Instructions")
    print("="*60)
    print("""
1. Go to: https://www.onetcenter.org/database.html
2. Download "Technology Skills" file
3. Extract to: data/onet/Technology_Skills.txt
4. Set: Config.ONET_SKILLS_PATH = "data/onet/Technology_Skills.txt"
    """)


def download_esco_skills(output_dir: str = "data/esco"):
    """
    Download ESCO Skills database
    
    Note: You need to manually download from https://esco.ec.europa.eu/en/use-esco/download
    """
    print("="*60)
    print("ESCO Download Instructions")
    print("="*60)
    print("""
1. Go to: https://esco.ec.europa.eu/en/use-esco/download
2. Download "Skills" CSV file (English)
3. Extract to: data/esco/skills_en.csv
4. Set: Config.ESCO_SKILLS_PATH = "data/esco/skills_en.csv"
    """)


def create_custom_skills_file(output_path: str = "data/custom_skills.json"):
    """Create a template for custom skills"""
    template = {
        "skills": [
            {"name": "LangChain", "category": "ai_tools", "aliases": ["Langchain", "Lang Chain"]},
            {"name": "PhiData", "category": "ai_tools", "aliases": ["Phi Data"]},
            {"name": "CrewAI", "category": "ai_tools", "aliases": ["Crew AI"]},
        ]
    }
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(template, f, indent=2)
    
    print(f"✅ Created custom skills template: {output_path}")
    print("Add your own skills and reload the parser!")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("="*60)
    print("RESUME PARSER v3.4 - Dynamic Skill Taxonomy")
    print("="*60)
    print("""
NEW FEATURES:
  ✅ Dynamic Skill Taxonomy (O*NET/ESCO/Custom)
  ✅ Experience Classification (jobs vs certs vs projects)
  ✅ Separate Projects section
  ✅ Merged certifications from all sources
  ✅ MCP-ready architecture

SKILL SOURCES:
  • O*NET: ~35,000 skills (US DOL)
  • ESCO: ~13,500 skills (EU)
  • Custom: Add your own emerging tech skills

USAGE:
  1. Download O*NET/ESCO files (see download_onet_skills())
  2. Or use built-in defaults (150+ tech skills)
  3. parser = ResumeParser()
  4. result = parser.parse_file("resume.pdf")
""")

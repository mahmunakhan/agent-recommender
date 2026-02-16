"""
Embedding Service
Generates vector embeddings using sentence-transformers
"""

from sentence_transformers import SentenceTransformer
import logging
from typing import List, Optional
import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating text embeddings"""
    
    def __init__(self):
        self.model = None
        self.model_name = settings.EMBEDDING_MODEL
    
    def load_model(self) -> bool:
        """Load the embedding model"""
        try:
            logger.info(f"Loading embedding model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            logger.info("Embedding model loaded successfully")
            return True
        except Exception as e:
            logger.error(f"Error loading embedding model: {e}")
            return False
    
    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding for a single text"""
        if self.model is None:
            self.load_model()
        
        try:
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None
    
    def generate_embeddings(self, texts: List[str]) -> Optional[List[List[float]]]:
        """Generate embeddings for multiple texts (batch)"""
        if self.model is None:
            self.load_model()
        
        try:
            embeddings = self.model.encode(texts, convert_to_numpy=True)
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            return None
    
    def generate_profile_embedding(self, profile_data: dict) -> Optional[List[float]]:
        """
        Generate embedding for a candidate profile.
        Combines headline, summary, skills, and experience.
        """
        parts = []
        
        # Add headline
        if profile_data.get("headline"):
            parts.append(profile_data["headline"])
        
        # Add summary
        if profile_data.get("summary"):
            parts.append(profile_data["summary"])
        
        # Add skills
        skills = profile_data.get("skills", [])
        if skills:
            if isinstance(skills[0], dict):
                skill_names = [s.get("name", "") for s in skills]
            else:
                skill_names = skills
            parts.append("Skills: " + ", ".join(skill_names))
        
        # Add experience titles
        experiences = profile_data.get("experience", [])
        if experiences:
            titles = [exp.get("title", "") for exp in experiences if exp.get("title")]
            if titles:
                parts.append("Experience: " + ", ".join(titles))
        
        # Add desired role
        if profile_data.get("desired_role"):
            parts.append(f"Seeking: {profile_data['desired_role']}")
        
        if not parts:
            logger.warning("No profile data to embed")
            return None
        
        text = " | ".join(parts)
        return self.generate_embedding(text)
    
    def generate_job_embedding(self, job_data: dict) -> Optional[List[float]]:
        """
        Generate embedding for a job posting.
        Combines title, company, description, and required skills.
        """
        parts = []
        
        # Add title
        if job_data.get("title"):
            parts.append(job_data["title"])
        
        # Add company
        if job_data.get("company_name"):
            parts.append(f"at {job_data['company_name']}")
        
        # Add description (truncate if too long)
        description = job_data.get("description_clean") or job_data.get("description_raw", "")
        if description:
            # Truncate to first 500 chars for embedding
            parts.append(description[:500])
        
        # Add required skills
        required_skills = job_data.get("required_skills", [])
        if required_skills:
            if isinstance(required_skills[0], dict):
                skill_names = [s.get("skill_name", "") for s in required_skills]
            else:
                skill_names = required_skills
            parts.append("Required: " + ", ".join(skill_names))
        
        if not parts:
            logger.warning("No job data to embed")
            return None
        
        text = " | ".join(parts)
        return self.generate_embedding(text)
    
    def compute_similarity(
        self, 
        embedding1: List[float], 
        embedding2: List[float]
    ) -> float:
        """Compute cosine similarity between two embeddings"""
        try:
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)
            
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            return float(dot_product / (norm1 * norm2))
        except Exception as e:
            logger.error(f"Error computing similarity: {e}")
            return 0.0
    
    def get_model_info(self) -> dict:
        """Get information about the loaded model"""
        if self.model is None:
            return {"loaded": False, "model_name": self.model_name}
        
        return {
            "loaded": True,
            "model_name": self.model_name,
            "embedding_dimension": self.model.get_sentence_embedding_dimension()
        }


# Global instance
embedding_service = EmbeddingService()
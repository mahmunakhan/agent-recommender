"""
Milvus Vector Database Service
Handles vector storage and similarity search
"""

from pymilvus import (
    connections,
    Collection,
    FieldSchema,
    CollectionSchema,
    DataType,
    utility
)
import logging
from typing import List, Optional
import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

# Collection names
PROFILE_COLLECTION = "profile_embeddings"
JOB_COLLECTION = "job_embeddings"

# Vector dimension (all-MiniLM-L6-v2 produces 384-dim vectors)
VECTOR_DIM = 384


class MilvusService:
    """Service for Milvus vector operations"""
    
    def __init__(self):
        self.connected = False
    
    def connect(self) -> bool:
        """Connect to Milvus"""
        try:
            connections.connect(
                alias="default",
                host=settings.MILVUS_HOST,
                port=settings.MILVUS_PORT
            )
            self.connected = True
            logger.info("Connected to Milvus")
            return True
        except Exception as e:
            logger.error(f"Milvus connection failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from Milvus"""
        try:
            connections.disconnect("default")
            self.connected = False
            logger.info("Disconnected from Milvus")
        except Exception as e:
            logger.error(f"Milvus disconnect error: {e}")
    
    def create_collections(self):
        """Create profile and job embedding collections"""
        
        # Profile embeddings collection
        if not utility.has_collection(PROFILE_COLLECTION):
            profile_fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="profile_id", dtype=DataType.VARCHAR, max_length=36),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=VECTOR_DIM)
            ]
            profile_schema = CollectionSchema(
                fields=profile_fields,
                description="Profile embeddings for semantic search"
            )
            Collection(name=PROFILE_COLLECTION, schema=profile_schema)
            logger.info(f"Created collection: {PROFILE_COLLECTION}")
        
        # Job embeddings collection
        if not utility.has_collection(JOB_COLLECTION):
            job_fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="job_id", dtype=DataType.VARCHAR, max_length=36),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=VECTOR_DIM)
            ]
            job_schema = CollectionSchema(
                fields=job_fields,
                description="Job embeddings for semantic search"
            )
            Collection(name=JOB_COLLECTION, schema=job_schema)
            logger.info(f"Created collection: {JOB_COLLECTION}")
    
    def create_indexes(self):
        """Create IVF_FLAT indexes for fast similarity search"""
        
        index_params = {
            "metric_type": "COSINE",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128}
        }
        
        # Profile index
        if utility.has_collection(PROFILE_COLLECTION):
            collection = Collection(PROFILE_COLLECTION)
            if not collection.has_index():
                collection.create_index(field_name="embedding", index_params=index_params)
                logger.info(f"Created index for {PROFILE_COLLECTION}")
        
        # Job index
        if utility.has_collection(JOB_COLLECTION):
            collection = Collection(JOB_COLLECTION)
            if not collection.has_index():
                collection.create_index(field_name="embedding", index_params=index_params)
                logger.info(f"Created index for {JOB_COLLECTION}")
    
    def insert_profile_embedding(self, profile_id: str, embedding: List[float]) -> bool:
        """Insert a profile embedding"""
        try:
            collection = Collection(PROFILE_COLLECTION)
            collection.insert([[profile_id], [embedding]])
            collection.flush()
            return True
        except Exception as e:
            logger.error(f"Error inserting profile embedding: {e}")
            return False
    
    def insert_job_embedding(self, job_id: str, embedding: List[float]) -> bool:
        """Insert a job embedding"""
        try:
            collection = Collection(JOB_COLLECTION)
            collection.insert([[job_id], [embedding]])
            collection.flush()
            return True
        except Exception as e:
            logger.error(f"Error inserting job embedding: {e}")
            return False
    
    def search_similar_jobs(
        self, 
        query_embedding: List[float], 
        top_k: int = 20
    ) -> List[dict]:
        """Search for similar jobs given a profile embedding"""
        try:
            collection = Collection(JOB_COLLECTION)
            collection.load()
            
            search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}
            
            results = collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                output_fields=["job_id"]
            )
            
            matches = []
            for hits in results:
                for hit in hits:
                    matches.append({
                        "job_id": hit.entity.get("job_id"),
                        "similarity": hit.score
                    })
            
            return matches
        except Exception as e:
            logger.error(f"Error searching jobs: {e}")
            return []
    
    def search_similar_profiles(
        self, 
        query_embedding: List[float], 
        top_k: int = 20
    ) -> List[dict]:
        """Search for similar profiles given a job embedding"""
        try:
            collection = Collection(PROFILE_COLLECTION)
            collection.load()
            
            search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}
            
            results = collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                output_fields=["profile_id"]
            )
            
            matches = []
            for hits in results:
                for hit in hits:
                    matches.append({
                        "profile_id": hit.entity.get("profile_id"),
                        "similarity": hit.score
                    })
            
            return matches
        except Exception as e:
            logger.error(f"Error searching profiles: {e}")
            return []
    
    def get_collection_stats(self) -> dict:
        """Get statistics for all collections"""
        stats = {}
        
        for name in [PROFILE_COLLECTION, JOB_COLLECTION]:
            if utility.has_collection(name):
                collection = Collection(name)
                stats[name] = {
                    "exists": True,
                    "num_entities": collection.num_entities
                }
            else:
                stats[name] = {"exists": False, "num_entities": 0}
        
        return stats


# Global instance
milvus_service = MilvusService()
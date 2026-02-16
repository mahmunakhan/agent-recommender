"""
MinIO Object Storage Service
Handles resume file uploads and downloads
"""

from minio import Minio
from minio.error import S3Error
import logging
from typing import Optional, BinaryIO
from datetime import timedelta
import io

from app.config import settings

logger = logging.getLogger(__name__)


class MinioService:
    """Service for MinIO object storage operations"""
    
    def __init__(self):
        self.client = None
        self.bucket_name = settings.MINIO_BUCKET
    
    def connect(self) -> bool:
        """Initialize MinIO client"""
        try:
            self.client = Minio(
                f"{settings.MINIO_HOST}:{settings.MINIO_PORT}",
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=False  # Set True for HTTPS
            )
            logger.info("MinIO client initialized")
            return True
        except Exception as e:
            logger.error(f"MinIO connection failed: {e}")
            return False
    
    def create_bucket(self) -> bool:
        """Create the resumes bucket if it doesn't exist"""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(f"Created bucket: {self.bucket_name}")
            else:
                logger.info(f"Bucket already exists: {self.bucket_name}")
            return True
        except S3Error as e:
            logger.error(f"Error creating bucket: {e}")
            return False
    
    def upload_resume(
        self, 
        file_data: BinaryIO, 
        filename: str,
        content_type: str = "application/pdf"
    ) -> Optional[str]:
        """
        Upload a resume file to MinIO.
        Returns the object path if successful.
        """
        try:
            # Get file size
            file_data.seek(0, 2)  # Seek to end
            file_size = file_data.tell()
            file_data.seek(0)  # Reset to beginning
            
            # Upload file
            object_name = f"resumes/{filename}"
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                data=file_data,
                length=file_size,
                content_type=content_type
            )
            
            logger.info(f"Uploaded: {object_name}")
            return object_name
            
        except S3Error as e:
            logger.error(f"Error uploading file: {e}")
            return None
    
    def download_resume(self, object_name: str) -> Optional[bytes]:
        """Download a resume file from MinIO"""
        try:
            response = self.client.get_object(
                bucket_name=self.bucket_name,
                object_name=object_name
            )
            data = response.read()
            response.close()
            response.release_conn()
            return data
        except S3Error as e:
            logger.error(f"Error downloading file: {e}")
            return None
    
    def get_presigned_url(
        self, 
        object_name: str, 
        expires_hours: int = 1
    ) -> Optional[str]:
        """Get a presigned URL for temporary file access"""
        try:
            url = self.client.presigned_get_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                expires=timedelta(hours=expires_hours)
            )
            return url
        except S3Error as e:
            logger.error(f"Error generating presigned URL: {e}")
            return None
    
    def delete_resume(self, object_name: str) -> bool:
        """Delete a resume file from MinIO"""
        try:
            self.client.remove_object(
                bucket_name=self.bucket_name,
                object_name=object_name
            )
            logger.info(f"Deleted: {object_name}")
            return True
        except S3Error as e:
            logger.error(f"Error deleting file: {e}")
            return False
    
    def list_resumes(self, prefix: str = "resumes/") -> list:
        """List all resume files"""
        try:
            objects = self.client.list_objects(
                bucket_name=self.bucket_name,
                prefix=prefix,
                recursive=True
            )
            return [obj.object_name for obj in objects]
        except S3Error as e:
            logger.error(f"Error listing files: {e}")
            return []
    
    def get_stats(self) -> dict:
        """Get storage statistics"""
        try:
            bucket_exists = self.client.bucket_exists(self.bucket_name)
            file_count = len(self.list_resumes()) if bucket_exists else 0
            
            return {
                "bucket": self.bucket_name,
                "exists": bucket_exists,
                "file_count": file_count
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {"error": str(e)}


# Global instance
minio_service = MinioService()
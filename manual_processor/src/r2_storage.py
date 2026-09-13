"""
Cloudflare R2 Storage Utility for Pages Functions
Provides S3-compatible interface for file storage
"""

import os
import json
import uuid
from typing import Optional, BinaryIO, Dict, Any, List
from datetime import datetime, timedelta
from pathlib import Path
import mimetypes


class R2Storage:
    """R2 storage client for Pages Functions"""
    
    def __init__(self, binding: Any = None):
        """
        Initialize R2 storage.
        
        Args:
            binding: Cloudflare R2 binding from Pages Functions context.env.FILES
        """
        self.binding = binding
        self.bucket_name = os.getenv("R2_BUCKET_NAME", "manual-processor-files")
    
    def _get_client(self):
        """Get R2 client from binding"""
        if self.binding:
            return self.binding
        # Fallback for local development - use boto3 with localstack or MinIO
        try:
            import boto3
            return boto3.client(
                's3',
                endpoint_url=os.getenv("R2_ENDPOINT_URL"),
                aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
                region_name="auto"
            )
        except ImportError:
            raise RuntimeError("No R2 binding available and boto3 not installed")
    
    def upload_file(
        self, 
        file_data: bytes, 
        key: str, 
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Upload file to R2"""
        client = self._get_client()
        
        if content_type is None:
            content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"
        
        extra_args = {"ContentType": content_type}
        if metadata:
            extra_args["Metadata"] = metadata
        
        client.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=file_data,
            **extra_args
        )
        
        return {
            "key": key,
            "bucket": self.bucket_name,
            "size": len(file_data),
            "content_type": content_type,
            "url": f"https://{os.getenv('R2_PUBLIC_URL', self.bucket_name)}/{key}"
        }
    
    def download_file(self, key: str) -> bytes:
        """Download file from R2"""
        client = self._get_client()
        response = client.get_object(Bucket=self.bucket_name, Key=key)
        return response['Body'].read()
    
    def delete_file(self, key: str) -> bool:
        """Delete file from R2"""
        client = self._get_client()
        client.delete_object(Bucket=self.bucket_name, Key=key)
        return True
    
    def list_files(self, prefix: str = "", limit: int = 1000) -> List[Dict[str, Any]]:
        """List files in R2"""
        client = self._get_client()
        response = client.list_objects_v2(
            Bucket=self.bucket_name,
            Prefix=prefix,
            MaxKeys=limit
        )
        return [
            {
                "key": obj["Key"],
                "size": obj["Size"],
                "last_modified": obj["LastModified"].isoformat() if obj.get("LastModified") else None,
                "etag": obj.get("ETag", "").strip('"')
            }
            for obj in response.get("Contents", [])
        ]
    
    def generate_presigned_url(
        self, 
        key: str, 
        expiration: int = 3600,
        method: str = "GET"
    ) -> str:
        """Generate presigned URL for direct access"""
        client = self._get_client()
        return client.generate_presigned_url(
            ClientMethod=f"{method.lower()}_object",
            Params={"Bucket": self.bucket_name, "Key": key},
            ExpiresIn=expiration
        )
    
    def file_exists(self, key: str) -> bool:
        """Check if file exists"""
        client = self._get_client()
        try:
            client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except Exception:
            return False


class FileManager:
    """High-level file management for manual processor"""
    
    def __init__(self, r2: R2Storage):
        self.r2 = r2
    
    def save_upload(self, file_id: str, filename: str, file_data: bytes) -> Dict[str, Any]:
        """Save uploaded PDF file"""
        key = f"uploads/{file_id}/{filename}"
        result = self.r2.upload_file(
            file_data, 
            key,
            content_type="application/pdf",
            metadata={"file_id": file_id, "original_filename": filename}
        )
        result["file_id"] = file_id
        result["filename"] = filename
        result["size_mb"] = round(len(file_data) / (1024 * 1024), 2)
        return result
    
    def save_result(self, file_id: str, result_type: str, file_data: bytes, filename: str) -> Dict[str, Any]:
        """Save processing result file"""
        key = f"results/{file_id}/{result_type}/{filename}"
        return self.r2.upload_file(
            file_data,
            key,
            metadata={"file_id": file_id, "result_type": result_type}
        )
    
    def save_json_result(self, file_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Save processing result as JSON"""
        key = f"results/{file_id}/result.json"
        return self.r2.upload_file(
            json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'),
            key,
            content_type="application/json",
            metadata={"file_id": file_id}
        )
    
    def get_result(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get processing result JSON"""
        key = f"results/{file_id}/result.json"
        if not self.r2.file_exists(key):
            return None
        data = self.r2.download_file(key)
        return json.loads(data.decode('utf-8'))
    
    def list_uploads(self) -> List[Dict[str, Any]]:
        """List all uploaded files"""
        return self.r2.list_files("uploads/")
    
    def cleanup_old_files(self, days: int = 7) -> int:
        """Clean up files older than specified days"""
        # Implementation would iterate and delete old files
        # For now, return 0
        return 0


# Global instance for dependency injection
_r2_storage: Optional[R2Storage] = None
_file_manager: Optional[FileManager] = None


def get_r2_storage(binding: Any = None) -> R2Storage:
    """Get or create R2 storage instance"""
    global _r2_storage
    if _r2_storage is None:
        _r2_storage = R2Storage(binding)
    return _r2_storage


def get_file_manager(binding: Any = None) -> FileManager:
    """Get or create FileManager instance"""
    global _file_manager
    if _file_manager is None:
        _file_manager = FileManager(get_r2_storage(binding))
    return _file_manager


def set_r2_binding(binding: Any) -> None:
    """Set R2 binding from Pages Functions context"""
    global _r2_storage, _file_manager
    _r2_storage = R2Storage(binding)
    _file_manager = FileManager(_r2_storage)
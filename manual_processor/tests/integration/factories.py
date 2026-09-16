"""
Test data factories for integration tests
"""
import factory
import random
import string
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from .utils.mock_services import TestDataFactory


class FileIdFactory(factory.Factory):
    """Factory for generating file IDs"""
    class Meta:
        # This is just for documentation - actual implementation below
        pass
    
    @classmethod
    def create(cls) -> str:
        """Generate a random 32-character hex string"""
        return ''.join(random.choices('0123456789abcdef', k=32))


class UserFactory(factory.Factory):
    """Factory for generating test users"""
    class Meta:
        pass
    
    @staticmethod
    def create_role(role: str = "user") -> Dict[str, Any]:
        """Create a user with specified role"""
        now = int(datetime.now().timestamp())
        exp = now + 3600  # 1 hour expiry
        
        return {
            "sub": f"user-{FileIdFactory.create()[:8]}",
            "email": f"user-{FileIdFactory.create()[:8]}@example.com",
            "role": role,
            "exp": exp,
            "iat": now
        }
    
    @staticmethod
    def create_jwt_token(user_data: Dict[str, Any], secret: str = "test-secret") -> str:
        """Create a JWT token from user data (simplified for testing)"""
        import base64
        
        # In real implementation, we'd properly sign this
        # For testing, we'll create a fake token that our mock validation will accept
        header = {"alg": "HS256", "typ": "JWT"}
        header_json = json.dumps(header, separators=(',', ':'))
        payload_json = json.dumps(user_data, separators=(',', ':'))
        
        header_b64 = base64.urlsafe_b64encode(header_json.encode()).decode().rstrip('=')
        payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode().rstrip('=')
        
        # For testing purposes, we'll use a signature that our mock validation accepts
        # In reality, this would be properly signed
        signature = "signature"
        
        return f"{header_b64}.{payload_b64}.{signature}"


class ProcessingOptionsFactory(factory.Factory):
    """Factory for generating processing options"""
    class Meta:
        pass
    
    @staticmethod
    def create(**kwargs) -> Dict[str, Any]:
        """Create processing options with optional overrides"""
        defaults = {
            "compact_layout": random.choice([True, False]),
            "use_emojis": random.choice([True, False]),
            "prompt_layout": random.choice(["horizontal", "vertical"]),
            "prompt_strict_mode": random.choice([True, False]),
            "prompt_has_diagrams": random.choice([True, False]),
            "prompt_low_quality_mode": random.choice([True, False]),
            "base_url": "http://localhost:8788"
        }
        defaults.update(kwargs)
        return defaults


class QueueMessageFactory(factory.Factory):
    """Factory for generating queue messages"""
    class Meta:
        pass
    
    @staticmethod
    def create(file_id: Optional[str] = None, 
               pdf_key: Optional[str] = None,
               options: Optional[Dict[str, Any]] = None,
               retry_count: int = 0) -> Dict[str, Any]:
        """Create a queue message"""
        if file_id is None:
            file_id = FileIdFactory.create()
        if pdf_key is None:
            pdf_key = f"uploads/{file_id}/test.pdf"
        if options is None:
            options = ProcessingOptionsFactory.create()
        
        return {
            "file_id": file_id,
            "pdf_key": pdf_key,
            "options": options,
            "timestamp": int(datetime.now().timestamp() * 1000),
            "retry_count": retry_count,
            "status": "pending"
        }


class WebSocketMessageFactory(factory.Factory):
    """Factory for generating WebSocket messages"""
    class Meta:
        pass
    
    @staticmethod
    def create_progress(file_id: str, status: str, progress: float, 
                       stage: str, result: Any = None, error: Any = None) -> Dict[str, Any]:
        """Create a progress WebSocket message"""
        message = {
            "type": "progress",
            "payload": {
                "file_id": file_id,
                "status": status,
                "progress": progress,
                "stage": stage
            }
        }
        if result is not None:
            message["payload"]["result"] = result
        if error is not None:
            message["payload"]["error"] = error
        return message
    
    @staticmethod
    def create_ping() -> Dict[str, Any]:
        """Create a ping message"""
        return {
            "type": "ping",
            "payload": {}
        }
    
    @staticmethod
    def create_pong() -> Dict[str, Any]:
        """Create a pong message"""
        return {
            "type": "pong",
            "payload": {}
        }


class ApiResponseFactory(factory.Factory):
    """Factory for generating expected API responses"""
    class Meta:
        pass
    
    @staticmethod
    def health_check() -> Dict[str, Any]:
        """Expected health check response"""
        return {
            "status": "ok",
            "service": "edge-worker",
            "version": "1.0.0",
            "timestamp": factory.LazyAttribute(lambda _: datetime.now().isoformat())
        }
    
    @staticmethod
    def config_response() -> Dict[str, Any]:
        """Expected config response"""
        return {
            "gemini_model_name": "gemini-1.5-flash",
            "processor_type": "gemini",
            "pdf_dpi": 300,
            "max_file_size_mb": 100,
            "web_upload_max_mb": 100,
            "output_directory": "/tmp/output",
            "supported_extensions": [".pdf"],
            "default_language": "ja"
        }
    
    @staticmethod
    def upload_success(file_id: str, filename: str, size_mb: float) -> Dict[str, Any]:
        """Expected successful upload response"""
        return {
            "key": f"uploads/{file_id}/{filename}",
            "bucket": "manual-processor-files-test",
            "size": int(size_mb * 1024 * 1024),
            "content_type": "application/pdf",
            "url": f"https://pub-xxxxxxxx.r2.dev/uploads/{file_id}/{filename}",
            "file_id": file_id,
            "filename": filename,
            "size_mb": round(size_mb, 2)
        }
    
    @staticmethod
    def process_queued(file_id: str) -> Dict[str, Any]:
        """Expected queued processing response"""
        return {
            "success": True,
            "file_id": file_id,
            "status": "queued",
            "message": "処理がキューに追加されました。進捗は WebSocket で確認できます。"
        }
    
    @staticmethod
    def processing_result(file_id: str, success: bool = True) -> Dict[str, Any]:
        """Expected processing result response"""
        base = TestDataFactory.create_sample_processing_result(file_id)
        base["success"] = success
        if not success:
            base["error"] = "Test error"
            base["output_files"] = {}
        return base
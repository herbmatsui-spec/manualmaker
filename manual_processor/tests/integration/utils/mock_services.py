"""
Mock services for integration testing
"""
import json
from typing import Dict, Any, List, Optional
from unittest.mock import Mock
from pathlib import Path
import base64


class MockR2Service:
    """Mock R2 (S3-compatible) storage service"""
    
    def __init__(self):
        self.objects: Dict[str, Dict[str, Any]] = {}
        self.bucket_name = "test-bucket"
    
    def put_object(self, Bucket: str, Key: str, Body: bytes, 
                   ContentType: Optional[str] = None, 
                   Metadata: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Store an object"""
        self.objects[Key] = {
            "Body": Body,
            "ContentType": ContentType,
            "Metadata": Metadata or {},
            "Size": len(Body)
        }
        return {
            "ETag": f'"{hash(Key)}"',
            "VersionId": "1"
        }
    
    def get_object(self, Bucket: str, Key: str) -> Dict[str, Any]:
        """Retrieve an object"""
        if Key not in self.objects:
            raise Exception(f"Object {Key} not found")
        
        obj = self.objects[Key]
        class MockBody:
            def __init__(self, data):
                self._data = data
            
            def read(self):
                return self._data
        
        return {
            "Body": MockBody(obj["Body"]),
            "ContentType": obj["ContentType"],
            "Metadata": obj["Metadata"],
            "ContentLength": obj["Size"],
            "ETag": obj.get("ETag", f'"{hash(Key)}"')
        }
    
    def delete_object(self, Bucket: str, Key: str) -> Dict[str, Any]:
        """Delete an object"""
        if Key in self.objects:
            del self.objects[Key]
        return {}
    
    def list_objects_v2(self, Bucket: str, Prefix: str = "", 
                       MaxKeys: int = 1000) -> Dict[str, Any]:
        """List objects with prefix"""
        contents = []
        for key, obj in self.objects.items():
            if key.startswith(Prefix):
                contents.append({
                    "Key": key,
                    "Size": obj["Size"],
                    "LastModified": None,  # Simplified
                    "ETag": obj.get("ETag", f'"{hash(key)}"').strip('"'),
                    "StorageClass": "STANDARD"
                })
        
        return {
            "Contents": contents[:MaxKeys],
            "IsTruncated": len(contents) > MaxKeys,
            "KeyCount": min(len(contents), MaxKeys),
            "MaxKeys": MaxKeys,
            "Prefix": Prefix
        }
    
    def head_object(self, Bucket: str, Key: str) -> Dict[str, Any]:
        """Get object metadata"""
        if Key not in self.objects:
            raise Exception(f"Object {Key} not found")
        
        obj = self.objects[Key]
        return {
            "ContentType": obj["ContentType"],
            "ContentLength": obj["Size"],
            "ETag": obj.get("ETag", f'"{hash(Key)}"'),
            "Metadata": obj["Metadata"]
        }
    
    def generate_presigned_url(self, ClientMethod: str, 
                              Params: Dict[str, Any], 
                              ExpiresIn: int = 3600) -> str:
        """Generate presigned URL"""
        bucket = Params.get("Bucket", self.bucket_name)
        key = Params.get("Key", "")
        return f"http://localhost:9000/{bucket}/{key}?Expires={ExpiresIn}&Signature=test"


class MockQueueService:
    """Mock Cloudflare Queue service"""
    
    def __init__(self):
        self.messages: List[Dict[str, Any]] = []
        self.dlq_messages: List[Dict[str, Any]] = []
        self.consumers = {}
    
    async def send(self, message: Dict[str, Any]):
        """Send a message to the queue"""
        # Add timestamp if not present
        if "timestamp" not in message:
            message["timestamp"] = int(time.time() * 1000)
        self.messages.append(message)
    
    def receive_messages(self, max_batch_size: int = 10) -> List[Dict[str, Any]]:
        """Receive messages from queue"""
        messages = self.messages[:max_batch_size]
        self.messages = self.messages[max_batch_size:]
        return messages
    
    def peek_messages(self, max_batch_size: int = 10) -> List[Dict[str, Any]]:
        """Peek at messages without removing them"""
        return self.messages[:max_batch_size]
    
    def send_to_dlq(self, message: Dict[str, Any]):
        """Send message to Dead Letter Queue"""
        if "dlq_timestamp" not in message:
            message["dlq_timestamp"] = int(time.time() * 1000)
        self.dlq_messages.append(message)
    
    def get_dlq_messages(self) -> List[Dict[str, Any]]:
        """Get DLQ messages"""
        return list(self.dlq_messages)
    
    def clear(self):
        """Clear all messages"""
        self.messages.clear()
        self.dlq_messages.clear()


class MockDurableObjectService:
    """Mock Cloudflare Durable Object service"""
    
    def __init__(self):
        self.stubs: Dict[str, Any] = {}
        self.storage: Dict[str, Any] = {}
        self.sessions: Dict[str, Any] = {}  # file_id -> session data
        self.websockets: Dict[str, List[Any]] = {}  # file_id -> list of websockets
    
    def id_from_name(self, name: str) -> str:
        """Convert name to ID"""
        return f"do-{name}"
    
    def get(self, id: str):
        """Get or create a stub"""
        if id not in self.stubs:
            stub = self.MockDoStub(self.storage, self.sessions, self.websockets, id)
            self.stubs[id] = stub
        return self.stubs[id]
    
    class MockDoStub:
        def __init__(self, storage, sessions, websockets, file_id: str):
            self.storage = storage
            self.sessions = sessions
            self.websockets = websockets
            self.file_id = file_id
        
        async def fetch(self, request):
            """Handle fetch requests to the DO"""
            # Parse URL
            url = str(getattr(request, 'url', ''))
            method = getattr(request, 'method', 'GET')
            
            # Extract file_id from URL path like /progress/{file_id}
            import re
            match = re.search(r'/progress/([^/]+)', url)
            if not match:
                # Return 404 for invalid path
                from types import SimpleNamespace
                resp = SimpleNamespace()
                resp.status = 404
                resp.headers = {"Content-Type": "application/json"}
                resp.body = b'{"error": "Not found"}'
                return resp
            
            file_id = match.group(1)
            
            if method == "GET":
                # Get current state
                state = self.storage.get(f"progress:{file_id}")
                if state is None:
                    from types import SimpleNamespace
                    resp = SimpleNamespace()
                    resp.status = 404
                    resp.headers = {"Content-Type": "application/json"}
                    resp.body = b'{"error": "Not found"}'
                    return resp
                else:
                    from types import SimpleNamespace
                    resp = SimpleNamespace()
                    resp.status = 200
                    resp.headers = {"Content-Type": "application/json"}
                    resp.body = json.dumps(state).encode()
                    return resp
            
            elif method == "POST":
                # Update state
                try:
                    data = json.loads(getattr(request, 'body', b'{}' or b'{}'))
                except (json.JSONDecodeError, AttributeError):
                    data = {}
                
                # Get or create state
                state = self.storage.get(f"progress:{self.file_id}")
                if state is None:
                    state = {
                        "file_id": self.file_id,
                        "status": "pending",
                        "progress": 0,
                        "stage": "待機中",
                        "result": None,
                        "error": None
                    }
                
                # Update state
                if "status" in data:
                    state["status"] = data["status"]
                if "progress" in data:
                    state["progress"] = data["progress"]
                if "stage" in data:
                    state["stage"] = data["stage"]
                if "result" in data:
                    state["result"] = data["result"]
                if "error" in data:
                    state["error"] = data["error"]
                
                # Persist
                self.storage[f"progress:{self.file_id}"] = state
                
                # Broadcast to websockets
                if self.file_id in self.websockets:
                    message = json.dumps(state)
                    for ws in self.websockets[self.file_id]:
                        try:
                            ws.send(message)
                        except:
                            pass  # Ignore send errors
                
                from types import SimpleNamespace
                resp = SimpleNamespace()
                resp.status = 200
                resp.headers = {"Content-Type": "application/json"}
                resp.body = b'{"success": true}'
                return resp
            
            elif method == "DELETE":
                # Delete state
                if f"progress:{self.file_id}" in self.storage:
                    del self.storage[f"progress:{self.file_id}"]
                
                # Close websockets
                if self.file_id in self.websockets:
                    for ws in self.websockets[self.file_id]:
                        try:
                            ws.close()
                        except:
                            pass
                    del self.websockets[self.file_id]
                
                from types import SimpleNamespace
                resp = SimpleNamespace()
                resp.status = 200
                resp.headers = {"Content-Type": "application/json"}
                resp.body = b'{"success": true}'
                return resp
            
            # WebSocket upgrade
            elif (method == "GET" and 
                  getattr(request, 'headers', {}).get('Upgrade', '').lower() == 'websocket'):
                # Create websocket pair
                from pyodide.ffi import create_once_callable
                # Simplified - in real tests we'd use proper WebSocket mocking
                from types import SimpleNamespace
                resp = SimpleNamespace()
                resp.status = 101  # Switching Protocols
                resp.headers = {
                    "Upgrade": "websocket",
                    "Connection": "Upgrade"
                }
                # Would normally return websocket object
                return resp
            
            else:
                from types import SimpleNamespace
                resp = SimpleNamespace()
                resp.status = 405
                resp.headers = {"Content-Type": "application/json"}
                resp.body = b'{"error": "Method not allowed"}'
                return resp


class MockKVService:
    """Mock Cloudflare KV namespace"""
    
    def __init__(self):
        self.store: Dict[str, Any] = {}
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value by key"""
        return self.store.get(key)
    
    async def set(self, key: str, value: Any, expirationTtl: Optional[int] = None):
        """Set value by key"""
        self.store[key] = value
        # TTL not implemented for simplicity in tests
    
    async def delete(self, key: str):
        """Delete key"""
        self.store.pop(key, None)
    
    async def list(self, prefix: str = "") -> List[str]:
        """List keys with prefix"""
        if prefix:
            return [k for k in self.store.keys() if k.startswith(prefix)]
        return list(self.store.keys())


class MockEnv:
    """Mock Cloudflare environment for testing"""
    
    def __init__(self):
        self.R2 = MockR2Service()
        self.QUEUE = MockQueueService()
        self.PROGRESS_DO = MockDurableObjectService()
        self.KV = MockKVService()
        self.ENVIRONMENT = "development"
        self.BASE_URL = "http://localhost:8788"
        self.ALLOWED_ORIGINS = "http://localhost:3000,http://localhost:8000,http://localhost:8788"


def create_test_env() -> MockEnv:
    """Create a complete test environment"""
    return MockEnv()


# Test data generators
class TestDataFactory:
    """Factory for generating test data"""
    
    @staticmethod
    def create_valid_pdf() -> bytes:
        """Create a minimal valid PDF"""
        return b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n>>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n0000000053 00000 n \n0000000102 00000 n \ntrailer\n<<\n/Size 4\n/Root 1 0 R\n>>\nstartxref\n149\n%%EOF"
    
    @staticmethod
    def create_valid_mermaid() -> str:
        """Create a valid Mermaid diagram"""
        return """graph TD
    A[Start] --> B{Is it working?}
    B -->|Yes| C[Great!]
    B -->|No| D[Fix it]
    C --> E[End]
    D --> E"""
    
    @staticmethod
    def create_invalid_mermaid() -> str:
        """Create an invalid Mermaid diagram"""
        return "This is not valid Mermaid syntax at all"
    
    @staticmethod
    def create_sample_processing_result(file_id: str = "test-file-id") -> Dict[str, Any]:
        """Create a sample processing result"""
        return {
            "success": True,
            "file_id": file_id,
            "title": "テストマニュアル",
            "summary": "これはテスト用のマニュアルです。",
            "key_points": [
                "重要ポイント1",
                "重要ポイント2", 
                "重要ポイント3"
            ],
            "output_files": {
                "pdf": f"results/{file_id}/pdf/document_{file_id}.pdf",
                "docx": f"results/{file_id}/docx/document_{file_id}.docx",
                "audio": f"results/{file_id}/audio/audio_{file_id}.mp3",
                "diagram": f"results/{file_id}/diagram/diagram_{file_id}.png",
                "diagram_markdown": f"results/{file_id}/diagram_markdown/diagram_{file_id}.md",
                "diagram_mermaid": f"results/{file_id}/diagram_mermaid/diagram_{file_id}.mmd"
            }
        }
"""
Test client for making requests to Pages Functions
"""
import json
import time
from typing import Dict, Any, Optional, List
from unittest.mock import Mock

import requests


class TestClient:
    """
    Test client for making requests to Pages Functions endpoints
    Handles authentication, headers, and common request patterns
    """
    
    def __init__(self, base_url: str = "http://localhost:8788"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.auth_token = None
        self.default_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    def set_auth_token(self, token: str):
        """Set JWT token for authentication"""
        self.auth_token = token
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def clear_auth(self):
        """Clear authentication"""
        self.auth_token = None
        self.session.headers.pop("Authorization", None)
    
    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Any = None, 
        params: Dict[str, Any] = None,
        files: Dict[str, Any] = None,
        headers: Dict[str, str] = None
    ) -> requests.Response:
        """Make HTTP request with error handling"""
        url = f"{self.base_url}{endpoint}"
        
        # Prepare headers
        request_headers = self.default_headers.copy()
        if headers:
            request_headers.update(headers)
        
        # Remove Content-Type for file uploads (let requests set it)
        if files:
            request_headers.pop("Content-Type", None)
        
        # Prepare data
        json_data = None
        if data is not None and not files:
            json_data = json.dumps(data)
        
        # Make request
        response = self.session.request(
            method=method,
            url=url,
            headers=request_headers,
            params=params,
            data=json_data,
            files=files,
            timeout=30
        )
        
        return response
    
    def get(self, endpoint: str, params: Dict[str, Any] = None, **kwargs) -> requests.Response:
        """GET request"""
        return self._make_request("GET", endpoint, params=params, **kwargs)
    
    def post(self, endpoint: str, data: Any = None, files: Dict[str, Any] = None, **kwargs) -> requests.Response:
        """POST request"""
        return self._make_request("POST", endpoint, data=data, files=files, **kwargs)
    
    def put(self, endpoint: str, data: Any = None, **kwargs) -> requests.Response:
        """PUT request"""
        return self._make_request("PUT", endpoint, data=data, **kwargs)
    
    def delete(self, endpoint: str, **kwargs) -> requests.Response:
        """DELETE request"""
        return self._make_request("DELETE", endpoint, **kwargs)
    
    def patch(self, endpoint: str, data: Any = None, **kwargs) -> requests.Response:
        """PATCH request"""
        return self._make_request("PATCH", endpoint, data=data, **kwargs)
    
    # Convenience methods for common API patterns
    
    def health_check(self) -> requests.Response:
        """Call health check endpoint"""
        return self.get("/api/health")
    
    def get_config(self) -> requests.Response:
        """Get configuration"""
        return self.get("/api/config")
    
    def get_i18n_languages(self) -> requests.Response:
        """Get available languages"""
        return self.get("/api/i18n/languages")
    
    def get_i18n_translations(self, lang: str) -> requests.Response:
        """Get translations for language"""
        return self.get(f"/api/i18n/translations/{lang}")
    
    def set_language(self, language: str) -> requests.Response:
        """Set current language"""
        return self.post("/api/i18n/set", data={"language": language})
    
    def detect_language(self, text: str) -> requests.Response:
        """Detect language from text"""
        return self.post("/api/i18n/detect", data={"text": text})
    
    def upload_file(self, file_content: bytes, filename: str = "test.pdf") -> requests.Response:
        """Upload a file"""
        files = {"file": (filename, file_content, "application/pdf")}
        return self.post("/api/upload", files=files)
    
    def list_uploads(self) -> requests.Response:
        """List uploaded files"""
        return self.get("/api/uploads")
    
    def delete_upload(self, file_id: str) -> requests.Response:
        """Delete uploaded file"""
        return self.delete(f"/api/upload/{file_id}")
    
    def process_pdf(self, file_id: str, options: Dict[str, Any] = None) -> requests.Response:
        """Start PDF processing"""
        if options is None:
            options = {}
        return self.post(f"/api/process/{file_id}", data=options)
    
    def get_result(self, file_id: str) -> requests.Response:
        """Get processing result"""
        return self.get(f"/api/results/{file_id}")
    
    def download_file(self, file_id: str, file_type: str) -> requests.Response:
        """Download generated file"""
        return self.get(f"/api/download/{file_id}/{file_type}")
    
    def validate_mermaid(self, code: str) -> requests.Response:
        """Validate Mermaid code"""
        return self.post("/api/mermaid/validate", data={"mermaid_code": code})
    
    def render_mermaid(self, code: str, theme: str = "default", width: int = 800, height: int = 600) -> requests.Response:
        """Render Mermaid to PNG"""
        return self.post("/api/mermaid/render", data={
            "mermaid_code": code,
            "theme": theme,
            "width": width,
            "height": height
        })
    
    def regenerate_mermaid(self, current_code: str, instruction: str) -> requests.Response:
        """Regenerate Mermaid using AI"""
        return self.post("/api/mermaid/regenerate", data={
            "current_code": current_code,
            "instruction": instruction
        })
    
    def save_mermaid(self, file_id: str, code: str, theme: str = "default", width: int = 800, height: int = 600) -> requests.Response:
        """Save Mermaid code and rebuild documents"""
        return self.post(f"/api/mermaid/save/{file_id}", data={
            "mermaid_code": code,
            "theme": theme,
            "width": width,
            "height": height
        })
    
    def get_security_status(self) -> requests.Response:
        """Get security status"""
        return self.get("/api/security/status")
    
    def get_audit_logs(self, limit: int = 100) -> requests.Response:
        """Get audit logs"""
        return self.get(f"/api/security/audit?limit={limit}")
    
    def mask_text(self, text: str) -> requests.Response:
        """Mask sensitive data in text"""
        return self.post("/api/security/mask", data={"text": text})
    
    def get_drive_status(self) -> requests.Response:
        """Get Google Drive status"""
        return self.get("/api/drive/status")
    
    def get_drive_auth_url(self) -> requests.Response:
        """Get Google Drive auth URL"""
        return self.get("/api/drive/auth")
    
    def drive_callback(self, code: str) -> requests.Response:
        """Handle Google Drive OAuth callback"""
        return self.get(f"/api/drive/callback?code={code}")
    
    def upload_to_drive(self, file_id: str) -> requests.Response:
        """Upload processing results to Google Drive"""
        return self.post(f"/api/drive/upload/{file_id}")
    
    def revoke_drive_auth(self) -> requests.Response:
        """Revoke Google Drive authentication"""
        return self.post("/api/drive/revoke")
    
    def get_metrics(self) -> requests.Response:
        """Get Prometheus metrics"""
        return self.get("/metrics")
    
    def get_observability_status(self) -> requests.Response:
        """Get observability status"""
        return self.get("/api/observability/status")
    
    def websocket_url(self, file_id: str, token: str = None) -> str:
        """Generate WebSocket URL for progress tracking"""
        base = self.base_url.replace("http://", "ws://").replace("https://", "wss://")
        url = f"{base}/ws/progress/{file_id}"
        if token:
            url += f"?token={token}"
        return url


class MockServices:
    """
    Mock services for testing without actual Cloudflare bindings
    """
    
    @staticmethod
    def create_mock_r2():
        """Create a mock R2 service"""
        class MockR2:
            def __init__(self):
                self.objects = {}
            
            def put_object(self, Bucket, Key, Body, ContentType=None, Metadata=None):
                self.objects[Key] = {
                    "Body": Body,
                    "ContentType": ContentType,
                    "Metadata": Metadata or {}
                }
            
            def get_object(self, Bucket, Key):
                if Key not in self.objects:
                    raise Exception("Not found")
                body = self.objects[Key]["Body"]
                class MockBody:
                    def read(self):
                        return body
                return {"Body": MockBody()}
            
            def delete_object(self, Bucket, Key):
                if Key in self.objects:
                    del self.objects[Key]
            
            def list_objects_v2(self, Bucket, Prefix="", MaxKeys=1000):
                contents = []
                for key, obj in self.objects.items():
                    if key.startswith(Prefix):
                        contents.append({
                            "Key": key,
                            "Size": len(obj["Body"]),
                            "LastModified": None,
                            "ETag": '"test"'
                        })
                return {"Contents": contents[:MaxKeys]}
            
            def head_object(self, Bucket, Key):
                if Key not in self.objects:
                    raise Exception("Not found")
                return {}
            
            def generate_presigned_url(self, ClientMethod, Params, ExpiresIn):
                return f"http://localhost:9000/{Params['Bucket']}/{Params['Key']}"
        
        return MockR2()
    
    @staticmethod
    def create_mock_queue():
        """Create a mock Queue service"""
        class MockQueue:
            def __init__(self):
                self.messages = []
                self.sent_messages = []
            
            async def send(self, message):
                self.messages.append(message)
                self.sent_messages.append(message)
            
            def get_messages(self):
                return list(self.messages)
            
            def clear(self):
                self.messages.clear()
                self.sent_messages.clear()
        
        return MockQueue()
    
    @staticmethod
    def create_mock_progress_do():
        """Create a mock Progress Durable Object"""
        class MockProgressDO:
            def __init__(self):
                self.stubs = {}
                self.storage = {}
                self.sessions = {}  # file_id -> {websockets: set, state: dict}
            
            def id_from_name(self, name):
                return f"do-{name}"
            
            def get(self, id):
                if id not in self.stubs:
                    # Create a stub that can handle fetch requests
                    stub = MockDoStub(self.storage, self.sessions, id)
                    self.stubs[id] = stub
                return self.stubs[id]
            
            class MockDoStub:
                def __init__(self, storage, sessions, file_id):
                    self.storage = storage
                    self.sessions = sessions
                    self.file_id = file_id
                    self.websockets = set()
                
                async def fetch(self, request):
                    # Simplified fetch for testing
                    if hasattr(request, 'method'):
                        if request.method == "GET":
                            # Return current state
                            state = self.storage.get(f"progress:{self.file_id}")
                            if state is None:
                                # Return 404
                                from types import SimpleNamespace
                                resp = SimpleNamespace()
                                resp.status = 404
                                resp.headers = {}
                                resp.body = b'{"error": "Not found"}'
                                return resp
                            else:
                                from types import SimpleNamespace
                                resp = SimpleNamespace()
                                resp.status = 200
                                resp.headers = {"Content-Type": "application/json"}
                                resp.body = json.dumps(state).encode()
                                return resp
                        elif request.method == "POST":
                            # Update state
                            try:
                                data = json.loads(request.body) if hasattr(request, 'body') else {}
                            except:
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
                            
                            from types import SimpleNamespace
                            resp = SimpleNamespace()
                            resp.status = 200
                            resp.headers = {"Content-Type": "application/json"}
                            resp.body = b'{"success": true}'
                            return resp
                        elif request.method == "DELETE":
                            # Delete state
                            if f"progress:{self.file_id}" in self.storage:
                                del self.storage[f"progress:{self.file_id}"]
                            
                            from types import SimpleNamespace
                            resp = SimpleNamespace()
                            resp.status = 200
                            resp.headers = {"Content-Type": "application/json"}
                            resp.body = b'{"success": true}'
                            return resp
                    
                    # Default response
                    from types import SimpleNamespace
                    resp = SimpleNamespace()
                    resp.status = 405
                    resp.headers = {"Content-Type": "application/json"}
                    resp.body = b'{"error": "Method not allowed"}'
                    return resp
        
        return MockProgressDO()
    
    @staticmethod
    def create_mock_kv():
        """Create a mock KV service"""
        class MockKV:
            def __init__(self):
                self.store = {}
            
            async def get(self, key):
                return self.store.get(key)
            
            async def set(self, key, value, expirationTtl=None):
                self.store[key] = value
                # Simple TTL (not implemented for tests)
        
        return MockKV()
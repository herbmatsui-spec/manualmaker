"""
Pytest configuration and fixtures for integration tests
"""
import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Set test environment before importing application modules
os.environ["ENVIRONMENT"] = "development"
os.environ["GOOGLE_API_KEY"] = "test-key"
os.environ["GEMINI_API_KEY"] = "test-key"
os.environ["ENCRYPTION_KEY"] = "dGVzdC1lbmNyeXB0aW9uLWtleS10ZXN0LWVuY3J5cHRpb24ta2V5"  # base64 encoded
os.environ["R2_ENDPOINT_URL"] = "http://localhost:9000"
os.environ["R2_ACCESS_KEY_ID"] = "minioadmin"
os.environ["R2_SECRET_ACCESS_KEY"] = "minioadmin"
os.environ["R2_BUCKET_NAME"] = "manual-processor-files-test"
os.environ["BASE_URL"] = "http://localhost:8788"
os.environ["ALLOWED_ORIGINS"] = "http://localhost:3000,http://localhost:8000,http://localhost:8788"


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_r2_binding():
    """Create a mock R2 binding"""
    mock = Mock()
    mock.objects = {}
    
    def put_object(Bucket, Key, Body, ContentType=None, Metadata=None):
        mock.objects[Key] = {
            "Body": Body,
            "ContentType": ContentType,
            "Metadata": Metadata or {}
        }
    
    def get_object(Bucket, Key):
        if Key not in mock.objects:
            raise Exception("Not found")
        return {"Body": type('obj', (object,), {"read": lambda: mock.objects[Key]["Body"]})()}
    
    def delete_object(Bucket, Key):
        if Key in mock.objects:
            del mock.objects[Key]
    
    def list_objects_v2(Bucket, Prefix="", MaxKeys=1000):
        contents = []
        for key, obj in mock.objects.items():
            if key.startswith(Prefix):
                contents.append({
                    "Key": key,
                    "Size": len(obj["Body"]),
                    "LastModified": None,
                    "ETag": '"test"'
                })
        return {"Contents": contents[:MaxKeys]}
    
    def head_object(Bucket, Key):
        if Key not in mock.objects:
            raise Exception("Not found")
        return {}
    
    def generate_presigned_url(ClientMethod, Params, ExpiresIn):
        return f"http://localhost:9000/{Params['Bucket']}/{Params['Key']}"
    
    mock.put_object = put_object
    mock.get_object = get_object
    mock.delete_object = delete_object
    mock.list_objects_v2 = list_objects_v2
    mock.head_object = head_object
    mock.generate_presigned_url = generate_presigned_url
    
    return mock


@pytest.fixture
def mock_queue_binding():
    """Create a mock Queue binding"""
    mock = Mock()
    mock.messages = []
    
    async def send(message):
        mock.messages.append(message)
    
    mock.send = send
    return mock


@pytest.fixture
def mock_progress_do_binding():
    """Create a mock Progress Durable Object binding"""
    mock = Mock()
    mock.stubs = {}
    
    def id_from_name(name):
        return f"do-{name}"
    
    def get(id):
        if id not in mock.stubs:
            # Create a new stub
            stub = Mock()
            mock.stubs[id] = stub
        return mock.stubs[id]
    
    mock.id_from_name = id_from_name
    mock.get = get
    
    return mock


@pytest.fixture
def mock_kv_binding():
    """Create a mock KV binding"""
    mock = Mock()
    mock.store = {}
    
    async def get(key):
        return mock.store.get(key)
    
    async def set(key, value, expirationTtl=None):
        mock.store[key] = value
        # Simple TTL implementation (not production-ready but works for tests)
        if expirationTtl:
            # In real tests, we'd need to handle expiration
            pass
    
    mock.get = get
    mock.set = set
    
    return mock


@pytest.fixture
def test_client(temp_dir, mock_r2_binding, mock_queue_binding, mock_progress_do_binding, mock_kv_binding):
    """Create a test client with mocked bindings"""
    # Import after setting environment variables
    from manual_processor.config.cloudflare_config import CloudflareBindings, CloudflareConfig
    
    bindings = CloudflareBindings(
        FILES=mock_r2_binding,
        PDF_QUEUE=mock_queue_binding,
        PROGRESS_DO=mock_progress_do_binding,
        RATE_LIMIT_KV=mock_kv_binding,
    )
    
    config = CloudflareConfig.from_bindings(bindings)
    return config, bindings


@pytest.fixture
def sample_pdf_bytes():
    """Create a minimal valid PDF for testing"""
    # Minimal PDF header + EOF
    return b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n>>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n0000000053 00000 n \n0000000102 00000 n \ntrailer\n<<\n/Size 4\n/Root 1 0 R\n>>\nstartxref\n149\n%%EOF"


@pytest.fixture
def sample_mermaid_valid():
    """Valid Mermaid diagram for testing"""
    return "graph TD\n    A[Start] --> B{Decision}\n    B -->|Yes| C[Action 1]\n    B -->|No| D[Action 2]\n    C --> E[End]\n    D --> E"


@pytest.fixture
def sample_mermaid_invalid():
    """Invalid Mermaid diagram for testing"""
    return "This is not valid Mermaid syntax"


@pytest.fixture
def sample_jwt_token():
    """Create a sample JWT token for testing"""
    import base64
    import json
    
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": "test-user-123",
        "email": "test@example.com",
        "role": "user",
        "exp": int((datetime.datetime.now() + datetime.timedelta(hours=1)).timestamp()),
        "iat": int(datetime.datetime.now().timestamp())
    }
    
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
    
    # In real tests, we'd need to sign this, but for now we'll return unsigned
    # The validation will fail, but we can test the validation logic
    return f"{header_b64}.{payload_b64}."
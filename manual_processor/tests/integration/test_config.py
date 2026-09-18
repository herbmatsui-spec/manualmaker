"""
Test environment configuration and setup
"""
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "manual_processor"))

# Test environment variables (should match conftest.py)
TEST_ENV_VARS = {
    "ENVIRONMENT": "development",
    "GOOGLE_API_KEY": "test-key",
    "GEMINI_API_KEY": "test-key",
    "ENCRYPTION_KEY": "dGVzdC1lbmNyeXB0aW9uLWtleS10ZXN0LWVuY3J5cHRpb24ta2V5",
    "R2_ENDPOINT_URL": "http://localhost:9000",
    "R2_ACCESS_KEY_ID": "minioadmin",
    "R2_SECRET_ACCESS_KEY": "minioadmin",
    "R2_BUCKET_NAME": "manual-processor-files-test",
    "BASE_URL": "http://localhost:8788",
    "ALLOWED_ORIGINS": "http://localhost:3000,http://localhost:8000,http://localhost:8788",
}

def setup_test_environment():
    """Set up test environment variables"""
    for key, value in TEST_ENV_VARS.items():
        os.environ[key] = value

def reset_test_environment():
    """Reset environment variables to original state"""
    for key in TEST_ENV_VARS.keys():
        os.environ.pop(key, None)

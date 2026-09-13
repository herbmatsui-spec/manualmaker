"""
Simple integration test to verify core components work together
"""
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "manual_processor"))

# Setup test environment
from tests.integration.test_config import setup_test_environment
setup_test_environment()

# Test imports
from tests.integration.utils.test_client import TestClient
from tests.integration.utils.mock_services import TestDataFactory

def test_infrastructure_integration():
    """Test that core infrastructure components work together"""
    print("Testing infrastructure integration...")
    
    # 1. Test environment variables
    assert os.environ.get("ENVIRONMENT") == "development"
    assert os.environ.get("GOOGLE_API_KEY") == "test-key"
    assert os.environ.get("GEMINI_API_KEY") == "test-key"
    print("  ✓ Environment variables")
    
    # 2. Test test client creation
    client = TestClient("http://localhost:8788")
    assert client.base_url == "http://localhost:8788"
    print("  ✓ Test client")
    
    # 3. Test mock data creation
    pdf_data = TestDataFactory.create_valid_pdf()
    assert len(pdf_data) > 0
    assert pdf_data.startswith(b"%PDF")
    print("  ✓ Mock PDF data")
    
    mermaid_data = TestDataFactory.create_valid_mermaid()
    assert "graph TD" in mermaid_data
    assert "Start" in mermaid_data
    print("  ✓ Mock Mermaid data")
    
    # 4. Test that we can make a request (will fail without server, but client creation works)
    # This just tests that the client object is properly formed
    assert hasattr(client, 'get')
    assert hasattr(client, 'post')
    assert hasattr(client, 'health_check')
    print("  ✓ Test client methods")
    
    print("✅ Infrastructure integration test passed!")

if __name__ == "__main__":
    test_infrastructure_integration()
"""
Basic integration test to verify test setup works
"""
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "manual_processor"))

# Now import our test modules
from manual_processor.tests.integration.test_config import setup_test_environment, reset_test_environment
from manual_processor.tests.integration.utils.test_client import TestClient
from manual_processor.tests.integration.utils.mock_services import TestDataFactory
from manual_processor.tests.integration.factories import FileIdFactory, ProcessingOptionsFactory


def test_environment_setup():
    """Test that environment setup works correctly"""
    # Check that test environment variables are set
    assert os.environ.get("ENVIRONMENT") == "development"
    assert os.environ.get("GOOGLE_API_KEY") == "test-key" or os.environ.get("GOOGLE_API_KEY") == "test-key"
    assert os.environ.get("GEMINI_API_KEY") == "test-key"
    print("✓ Environment setup verified")


def test_test_client_creation():
    """Test that we can create a test client"""
    client = TestClient("http://localhost:8788")
    assert client.base_url == "http://localhost:8788"
    assert client.auth_token is None
    print("✓ Test client creation verified")


def test_mock_services_creation():
    """Test that mock services can be created"""
    mock_r2 = TestDataFactory.create_valid_pdf()
    assert len(mock_r2) > 0
    assert mock_r2.startswith(b"%PDF")
    
    mermaid = TestDataFactory.create_valid_mermaid()
    assert "graph TD" in mermaid
    assert "Start" in mermaid
    assert "End" in mermaid
    print("✓ Mock services creation verified")


def test_file_id_factory():
    """Test file ID factory"""
    file_id1 = FileIdFactory.create()
    file_id2 = FileIdFactory.create()
    
    assert len(file_id1) == 32
    assert len(file_id2) == 32
    assert file_id1 != file_id2  # Very high probability
    assert all(c in '0123456789abcdef' for c in file_id1)
    print("✓ File ID factory verified")


def test_processing_options_factory():
    """Test processing options factory"""
    options = ProcessingOptionsFactory.create()
    
    assert isinstance(options["compact_layout"], bool)
    assert isinstance(options["use_emojis"], bool)
    assert options["prompt_layout"] in ["horizontal", "vertical"]
    assert isinstance(options["prompt_strict_mode"], bool)
    assert isinstance(options["prompt_has_diagrams"], bool)
    assert isinstance(options["prompt_low_quality_mode"], bool)
    assert options["base_url"] == "http://localhost:8788"
    print("✓ Processing options factory verified")


if __name__ == "__main__":
    # Run tests manually for verification
    test_environment_setup()
    test_test_client_creation()
    test_mock_services_creation()
    test_file_id_factory()
    test_processing_options_factory()
    print("\n✅ All basic infrastructure tests passed!")
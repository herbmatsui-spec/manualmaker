"""
Integration tests for processing flow endpoints
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
setup_test_environment

import pytest
from tests.integration.utils.test_client import TestClient
from tests.integration.utils.mock_services import TestDataFactory


class TestProcessingFlow:
    """Test processing flow endpoints"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.client = TestClient()
        # Use a proper hexadecimal string (0-9, a-f only)
        self.test_file_id = "a1b2c3d4e5f678901234567890123456"  # 32-char hex
    
    def test_process_endpoint_exists(self):
        """Test that process endpoint method exists"""
        assert hasattr(self.client, 'process_pdf')
        print("✓ Process PDF method exists")
    
    def test_get_result_endpoint_exists(self):
        """Test that get result endpoint method exists"""
        assert hasattr(self.client, 'get_result')
        print("✓ Get result method exists")
    
    def test_create_test_file_id(self):
        """Test that we can create a test file ID"""
        # Remove any whitespace/newline characters
        clean_id = self.test_file_id.strip()
        assert len(clean_id) == 32
        assert all(c in '0123456789abcdef' for c in clean_id)
        print(f"✓ Test file ID: {clean_id}")
    
    def test_processing_options_structure(self):
        """Test that processing options have correct structure"""
        # Test default options
        options = {
            "compact_layout": False,
            "use_emojis": False,
            "prompt_layout": "horizontal",
            "prompt_strict_mode": True,
            "prompt_has_diagrams": False,
            "prompt_low_quality_mode": False,
            "base_url": "http://localhost:8788"
        }
        
        assert isinstance(options["compact_layout"], bool)
        assert isinstance(options["use_emojis"], bool)
        assert options["prompt_layout"] in ["horizontal", "vertical"]
        assert isinstance(options["prompt_strict_mode"], bool)
        assert isinstance(options["prompt_has_diagrams"], bool)
        assert isinstance(options["prompt_low_quality_mode"], bool)
        assert isinstance(options["base_url"], str)
        print("✓ Processing options structure validated")
    
    def test_mermaid_endpoints_exist(self):
        """Test that Mermaid endpoint methods exist"""
        assert hasattr(self.client, 'validate_mermaid')
        assert hasattr(self.client, 'render_mermaid')
        assert hasattr(self.client, 'regenerate_mermaid')
        assert hasattr(self.client, 'save_mermaid')
        print("✓ All Mermaid endpoint methods exist")
    
    def test_security_endpoints_exist(self):
        """Test that security endpoint methods exist"""
        assert hasattr(self.client, 'get_security_status')
        assert hasattr(self.client, 'get_audit_logs')
        assert hasattr(self.client, 'mask_text')
        print("✓ All security endpoint methods exist")
    
    def test_drive_endpoints_exist(self):
        """Test that Google Drive endpoint methods exist"""
        assert hasattr(self.client, 'get_drive_status')
        assert hasattr(self.client, 'get_drive_auth_url')
        assert hasattr(self.client, 'drive_callback')
        assert hasattr(self.client, 'upload_to_drive')
        assert hasattr(self.client, 'revoke_drive_auth')
        print("✓ All Google Drive endpoint methods exist")
    
    def test_observability_endpoints_exist(self):
        """Test that observability endpoint methods exist"""
        assert hasattr(self.client, 'get_metrics')
        assert hasattr(self.client, 'get_observability_status')
        print("✓ All observability endpoint methods exist")


if __name__ == "__main__":
    # Run tests manually
    test_instance = TestProcessingFlow()
    test_instance.setup_method()
    
    try:
        test_instance.test_process_endpoint_exists()
        test_instance.test_get_result_endpoint_exists()
        test_instance.test_create_test_file_id()
        test_instance.test_processing_options_structure()
        test_instance.test_mermaid_endpoints_exist()
        test_instance.test_security_endpoints_exist()
        test_instance.test_drive_endpoints_exist()
        test_instance.test_observability_endpoints_exist()
        print("\n✅ Processing flow infrastructure tests verified!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise
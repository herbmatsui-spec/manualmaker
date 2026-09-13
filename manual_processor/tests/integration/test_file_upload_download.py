"""
Integration tests for file upload and download endpoints
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


class TestFileUploadDownload:
    """Test file upload and download endpoints"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.client = TestClient()
        self.test_pdf = TestDataFactory.create_valid_pdf()
    
    def test_upload_endpoint_exists(self):
        """Test that upload endpoint method exists"""
        assert hasattr(self.client, 'upload_file')
        print("✓ Upload file method exists")
    
    def test_list_uploads_endpoint_exists(self):
        """Test that list uploads endpoint method exists"""
        assert hasattr(self.client, 'list_uploads')
        print("✓ List uploads method exists")
    
    def test_delete_upload_endpoint_exists(self):
        """Test that delete upload endpoint method exists"""
        assert hasattr(self.client, 'delete_upload')
        print("✓ Delete upload method exists")
    
    def test_download_endpoint_exists(self):
        """Test that download endpoint method exists"""
        assert hasattr(self.client, 'download_file')
        print("✓ Download file method exists")
    
    def test_create_valid_pdf(self):
        """Test that we can create a valid PDF for testing"""
        pdf_data = TestDataFactory.create_valid_pdf()
        assert len(pdf_data) > 0
        assert pdf_data.startswith(b"%PDF")
        assert b"%EOF" in pdf_data
        print(f"✓ Valid PDF created (size: {len(pdf_data)} bytes)")
    
    def test_pdf_structure(self):
        """Test that our test PDF has basic PDF structure"""
        pdf_data = TestDataFactory.create_valid_pdf()
        # Check for basic PDF elements
        assert b"%PDF" in pdf_data
        assert b"endobj" in pdf_data
        assert b"xref" in pdf_data
        assert b"trailer" in pdf_data
        assert b"%EOF" in pdf_data
        print("✓ PDF structure validated")


if __name__ == "__main__":
    # Run tests manually
    test_instance = TestFileUploadDownload()
    test_instance.setup_method()
    
    try:
        test_instance.test_upload_endpoint_exists()
        test_instance.test_list_uploads_endpoint_exists()
        test_instance.test_delete_upload_endpoint_exists()
        test_instance.test_download_endpoint_exists()
        test_instance.test_create_valid_pdf()
        test_instance.test_pdf_structure()
        print("\n✅ File Upload/Download infrastructure tests verified!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise
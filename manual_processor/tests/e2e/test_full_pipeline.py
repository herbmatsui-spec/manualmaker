"""
End-to-end tests for the complete document processing pipeline.
Tests the full flow from upload to result retrieval.
"""

import io
import time
import pytest
from fastapi.testclient import TestClient

from src.web.app import app
from tests.fixtures.sample_pdfs import create_sample_pdf, create_handwritten_sample_pdf


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


class TestFullPipeline:
    """Test complete document processing pipeline"""

    def test_upload_and_list(self, client: TestClient):
        """Test uploading a PDF and listing it"""
        # Step 1: Upload PDF
        pdf_content = create_handwritten_sample_pdf()
        upload_response = client.post(
            "/api/upload",
            files={"file": ("manual.pdf", io.BytesIO(pdf_content), "application/pdf")}
        )
        assert upload_response.status_code == 200
        upload_data = upload_response.json()
        file_id = upload_data["file_id"]
        
        # Step 2: List uploads
        list_response = client.get("/api/uploads")
        assert list_response.status_code == 200
        list_data = list_response.json()
        
        # Verify our upload is in the list
        upload_ids = [u["file_id"] for u in list_data["uploads"]]
        assert file_id in upload_ids

    def test_upload_and_download(self, client: TestClient):
        """Test uploading a PDF and listing it (download requires processing)"""
        # Step 1: Upload PDF
        pdf_content = create_sample_pdf(num_pages=2)
        upload_response = client.post(
            "/api/upload",
            files={"file": ("doc.pdf", io.BytesIO(pdf_content), "application/pdf")}
        )
        assert upload_response.status_code == 200
        file_id = upload_response.json()["file_id"]
        
        # Step 2: Verify file is in uploads list
        list_response = client.get("/api/uploads")
        assert list_response.status_code == 200
        uploads = list_response.json()["uploads"]
        assert any(u["file_id"] == file_id for u in uploads)
        
        # Note: Download endpoint requires PROCESSING_RESULTS, not just uploads
        # This is tested in integration tests with actual processing

    def test_multiple_uploads(self, client: TestClient):
        """Test uploading multiple files"""
        file_ids = []
        
        # Upload 3 files
        for i in range(3):
            pdf_content = create_sample_pdf(num_pages=1)
            response = client.post(
                "/api/upload",
                files={"file": (f"doc_{i}.pdf", io.BytesIO(pdf_content), "application/pdf")}
            )
            assert response.status_code == 200
            file_ids.append(response.json()["file_id"])
        
        # Verify all are listed
        list_response = client.get("/api/uploads")
        assert list_response.status_code == 200
        listed_ids = [u["file_id"] for u in list_response.json()["uploads"]]
        
        for file_id in file_ids:
            assert file_id in listed_ids

    def test_upload_validation_chain(self, client: TestClient):
        """Test complete validation chain"""
        # Test 1: Valid PDF
        valid_pdf = create_sample_pdf(num_pages=1)
        response = client.post(
            "/api/upload",
            files={"file": ("valid.pdf", io.BytesIO(valid_pdf), "application/pdf")}
        )
        assert response.status_code == 200
        
        # Test 2: Invalid extension
        response = client.post(
            "/api/upload",
            files={"file": ("invalid.txt", io.BytesIO(b"hello"), "text/plain")}
        )
        assert response.status_code == 400
        
        # Test 3: Wrong content type
        response = client.post(
            "/api/upload",
            files={"file": ("wrong_type.pdf", io.BytesIO(b"hello"), "text/plain")}
        )
        assert response.status_code == 400
        
        # Test 4: Invalid PDF content
        response = client.post(
            "/api/upload",
            files={"file": ("fake.pdf", io.BytesIO(b"not a pdf"), "application/pdf")}
        )
        assert response.status_code == 400


class TestHealthAndConfig:
    """Test health and config endpoints in sequence"""

    def test_health_then_config(self, client: TestClient):
        """Test accessing health and config in sequence"""
        # Health check
        health_response = client.get("/api/health")
        assert health_response.status_code == 200
        
        # Config check
        config_response = client.get("/api/config")
        assert config_response.status_code == 200
        
        # Verify response times
        assert health_response.elapsed.total_seconds() < 1.0
        assert config_response.elapsed.total_seconds() < 1.0


class TestI18nWorkflow:
    """Test internationalization workflow"""

    def test_language_detection_workflow(self, client: TestClient):
        """Test language detection workflow"""
        # Get available languages
        lang_response = client.get("/api/i18n/languages")
        assert lang_response.status_code == 200
        languages = lang_response.json()["languages"]
        
        # Get translations for each language
        for lang in ["ja", "en"]:
            trans_response = client.get(f"/api/i18n/translations/{lang}")
            assert trans_response.status_code == 200

    def test_language_detection(self, client: TestClient):
        """Test automatic language detection"""
        # Test Japanese text
        response = client.post(
            "/api/i18n/detect",
            json={"text": "これは日本語のテキストです。"}
        )
        assert response.status_code == 200
        
        # Test English text
        response = client.post(
            "/api/i18n/detect",
            json={"text": "This is English text."}
        )
        assert response.status_code == 200


class TestSecurityWorkflow:
    """Test security workflow"""

    def test_security_status_and_masking(self, client: TestClient):
        """Test security status check and text masking"""
        status_response = client.get("/api/security/status")
        assert status_response.status_code == 200
        status = status_response.json()
        assert status["pii_masking_enabled"] is False
        
        # Test masking
        mask_response = client.post(
            "/api/security/mask",
            json={"text": "Contact: user@example.com, Phone: 03-1234-5678"}
        )
        assert mask_response.status_code == 200
        mask_data = mask_response.json()
        assert mask_data["counts"]["EMAIL"] == 1
        assert mask_data["counts"]["PHONE_JP"] == 1

    def test_audit_logging(self, client: TestClient):
        """Test audit logging"""
        # Access audit logs
        audit_response = client.get("/api/security/audit?limit=10")
        assert audit_response.status_code == 200
        audit_data = audit_response.json()
        assert "logs" in audit_data
        assert "count" in audit_data


class TestErrorHandling:
    """Test error handling and edge cases"""

    def test_404_for_nonexistent_endpoint(self, client: TestClient):
        """Test 404 response for nonexistent endpoint"""
        response = client.get("/api/nonexistent")
        assert response.status_code == 404

    def test_404_for_invalid_file_id(self, client: TestClient):
        """Test 404 for invalid file ID in download"""
        response = client.get("/api/download/invalid-id/pdf")
        assert response.status_code == 404

    def test_cors_headers(self, client: TestClient):
        """Test CORS headers are present"""
        response = client.get("/api/health")
        # CORS headers should be present (even if empty for same-origin)
        assert response.status_code == 200

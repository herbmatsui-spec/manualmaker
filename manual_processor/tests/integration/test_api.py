"""
Integration tests for API endpoints.
Tests the FastAPI web server endpoints with TestClient.
"""

import io
import pytest
from fastapi.testclient import TestClient

from src.web.app import app
from src.utils.validators import validate_pdf_content
from tests.fixtures.sample_pdfs import (
    create_sample_pdf,
    create_handwritten_sample_pdf,
    create_invalid_pdf,
)


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


class TestHealthEndpoint:
    """Test health check endpoint"""

    def test_health_check(self, client: TestClient):
        """Test /api/health returns ok status"""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "processor_type" in data


class TestConfigEndpoint:
    """Test config endpoint"""

    def test_get_public_config(self, client: TestClient):
        """Test /api/config returns public configuration"""
        response = client.get("/api/config")
        assert response.status_code == 200
        data = response.json()
        assert "gemini_model_name" in data
        assert "processor_type" in data
        assert "web_upload_max_mb" in data


class TestUploadEndpoint:
    """Test file upload endpoint"""

    def test_upload_valid_pdf(self, client: TestClient):
        """Test uploading a valid PDF file"""
        pdf_content = create_sample_pdf(num_pages=1)
        response = client.post(
            "/api/upload",
            files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")}
        )
        assert response.status_code == 200
        data = response.json()
        assert "file_id" in data
        assert "filename" in data
        assert data["filename"] == "test.pdf"

    def test_upload_invalid_extension(self, client: TestClient):
        """Test uploading file with invalid extension"""
        response = client.post(
            "/api/upload",
            files={"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")}
        )
        assert response.status_code == 400
        assert "PDF" in response.json()["detail"]

    def test_upload_wrong_content_type(self, client: TestClient):
        """Test uploading with wrong content type"""
        pdf_content = create_sample_pdf(num_pages=1)
        response = client.post(
            "/api/upload",
            files={"file": ("test.pdf", io.BytesIO(pdf_content), "text/plain")}
        )
        assert response.status_code == 400
        assert "Content-Type" in response.json()["detail"]

    def test_upload_invalid_pdf_content(self, client: TestClient):
        """Test uploading file that's not actually a PDF"""
        invalid_content = create_invalid_pdf()
        response = client.post(
            "/api/upload",
            files={"file": ("test.pdf", io.BytesIO(invalid_content), "application/pdf")}
        )
        assert response.status_code == 400
        assert "PDF" in response.json()["detail"]

    def test_upload_too_large(self, client: TestClient):
        """Test uploading file that exceeds size limit"""
        # Create a PDF larger than default 100MB limit
        large_pdf = create_sample_pdf(num_pages=1) + b"x" * (101 * 1024 * 1024)
        response = client.post(
            "/api/upload",
            files={"file": ("large.pdf", io.BytesIO(large_pdf), "application/pdf")}
        )
        assert response.status_code == 400
        assert "サイズ" in response.json()["detail"] or "size" in response.json()["detail"].lower()


class TestUploadsListEndpoint:
    """Test uploads list endpoint"""

    def test_list_uploads_empty(self, client: TestClient):
        """Test listing uploads when none exist"""
        response = client.get("/api/uploads")
        assert response.status_code == 200
        data = response.json()
        assert "uploads" in data

    def test_list_uploads_after_upload(self, client: TestClient):
        """Test listing uploads after uploading a file"""
        # Upload a file first
        pdf_content = create_sample_pdf(num_pages=1)
        client.post(
            "/api/upload",
            files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")}
        )
        
        # List uploads
        response = client.get("/api/uploads")
        assert response.status_code == 200
        data = response.json()
        assert len(data["uploads"]) >= 1


class TestI18nEndpoints:
    """Test internationalization endpoints"""

    def test_get_languages(self, client: TestClient):
        """Test getting available languages"""
        response = client.get("/api/i18n/languages")
        assert response.status_code == 200
        data = response.json()
        assert "languages" in data
        assert "ja" in data["languages"]
        assert "en" in data["languages"]

    def test_get_translations_valid_lang(self, client: TestClient):
        """Test getting translations for valid language"""
        response = client.get("/api/i18n/translations/ja")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_get_translations_invalid_lang(self, client: TestClient):
        """Test getting translations for invalid language"""
        response = client.get("/api/i18n/translations/xx")
        assert response.status_code == 404


class TestSecurityEndpoints:
    """Test security endpoints"""

    def test_get_security_status(self, client: TestClient):
        """Test getting security status"""
        response = client.get("/api/security/status")
        assert response.status_code == 200
        data = response.json()
        assert "pii_masking_enabled" in data
        assert "audit_log_enabled" in data

    def test_mask_text(self, client: TestClient):
        """Test text masking endpoint"""
        response = client.post(
            "/api/security/mask",
            json={"text": "Email: test@example.com, Phone: 03-1234-5678"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "masked_text" in data
        assert "counts" in data
        assert "[REDACTED_EMAIL]" in data["masked_text"]

    def test_mask_empty_text(self, client: TestClient):
        """Test masking empty text"""
        response = client.post("/api/security/mask", json={"text": ""})
        assert response.status_code == 200
        data = response.json()
        assert data["masked_text"] == ""

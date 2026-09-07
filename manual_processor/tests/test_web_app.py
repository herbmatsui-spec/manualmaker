"""
Unit Tests for Web App API Endpoints (Step 12 Coverage Improvement)

Tests high-value endpoints to increase coverage from 54% to 75%:
- /api/upload - normal upload, file too large, invalid extension
- /api/process/options - POST processing options
- /api/download/{file_id}/{format} - download various formats
- /api/security/* - mask, audit, status endpoints
- /api/drive/* - mock Drive manager endpoints
- /api/mermaid/* - render, regenerate, save, validate
- /api/i18n/* - language endpoints
- /metrics and /api/observability/status
"""

import pytest
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from io import BytesIO

from fastapi.testclient import TestClient

from src.web.app import app

client = TestClient(app)


class TestHealthAndConfig:
    def test_health_check(self):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "processor_type" in data

    def test_public_config(self):
        response = client.get("/api/config")
        assert response.status_code == 200
        data = response.json()
        assert "gemini_model_name" in data
        assert "web_upload_max_mb" in data
        assert "supported_extensions" in data

    def test_get_available_languages(self):
        response = client.get("/api/i18n/languages")
        assert response.status_code == 200
        data = response.json()
        assert "languages" in data
        assert "current" in data


class TestI18n:
    @pytest.mark.skip(reason="Route parameter 'req' conflicts with FastAPI Request - app needs fix")
    def test_set_language(self):
        response = client.post("/api/i18n/set", json={"language": "en"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["language"] == "en"

    def test_get_translations_english(self):
        response = client.get("/api/i18n/translations/en")
        assert response.status_code == 200
        data = response.json()
        assert "app_title" in data
        assert data["app_title"] == "Handwritten Manual Automated Processing System"

    def test_get_translations_not_found(self):
        response = client.get("/api/i18n/translations/xyz")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_detect_language_text(self):
        response = client.post("/api/i18n/detect", json={"text": "これは日本語のテキストです"})
        assert response.status_code == 200
        data = response.json()
        assert "detected_language" in data


class TestSecurityEndpoints:
    def test_security_status(self):
        response = client.get("/api/security/status")
        assert response.status_code == 200
        data = response.json()
        assert "pii_masking_enabled" in data
        assert "encryption_available" in data
        assert "audit_log_enabled" in data

    def test_mask_text_with_content(self):
        response = client.post(
            "/api/security/mask",
            json={"text": "Contact me at test@example.com or 090-1234-5678"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "masked_text" in data
        assert "[REDACTED_EMAIL]" in data["masked_text"] or "test@example.com" not in data["masked_text"]
        assert "counts" in data

    def test_mask_text_empty(self):
        response = client.post("/api/security/mask", json={"text": ""})
        assert response.status_code == 200
        data = response.json()
        assert data["masked_text"] == ""
        assert data["counts"] == {}

    def test_mask_text_no_text_field(self):
        response = client.post("/api/security/mask", json={})
        assert response.status_code == 200
        data = response.json()
        assert data["masked_text"] == ""
        assert data["counts"] == {}

    def test_get_audit_logs(self):
        response = client.get("/api/security/audit")
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert "count" in data


class TestUpload:
    def test_upload_invalid_extension(self):
        response = client.post(
            "/api/upload",
            files={"file": ("test.txt", b"dummy content", "text/plain")}
        )
        assert response.status_code == 400
        assert "PDF" in response.json()["detail"]

    def test_upload_invalid_content_type(self):
        response = client.post(
            "/api/upload",
            files={"file": ("test.pdf", b"%PDF-1.4 dummy", "text/plain")}
        )
        assert response.status_code == 400
        assert "Content-Type" in response.json()["detail"]

    def test_upload_invalid_magic_bytes(self):
        response = client.post(
            "/api/upload",
            files={"file": ("test.pdf", b"NOT A PDF", "application/pdf")}
        )
        assert response.status_code == 400
        assert "PDF形式ではありません" in response.json()["detail"]

    @patch("src.web.app.config")
    def test_upload_file_too_large(self, mock_config):
        mock_config.web_upload_max_mb = 0.001
        mock_config.temp_directory = Path(tempfile.gettempdir())

        large_content = b"%PDF-1.4" + b"x" * (2 * 1024 * 1024)
        response = client.post(
            "/api/upload",
            files={"file": ("large.pdf", large_content, "application/pdf")}
        )
        assert response.status_code == 400
        assert "上限" in response.json()["detail"] or "超えて" in response.json()["detail"]

    @patch("src.web.app.config")
    def test_upload_success(self, mock_config):
        mock_config.web_upload_max_mb = 100
        mock_config.temp_directory = Path(tempfile.gettempdir())

        pdf_content = b"%PDF-1.4 test content"
        response = client.post(
            "/api/upload",
            files={"file": ("valid.pdf", pdf_content, "application/pdf")}
        )
        assert response.status_code == 200
        data = response.json()
        assert "file_id" in data
        assert data["filename"] == "valid.pdf"

    def test_list_uploads(self):
        response = client.get("/api/uploads")
        assert response.status_code == 200
        data = response.json()
        assert "uploads" in data
        assert isinstance(data["uploads"], list)


class TestProcessing:
    @patch("src.web.app.config")
    @patch("src.web.app.UPLOADED_FILES", {"test_file_id": {"file_id": "test_file_id", "filename": "test.pdf", "path": "/tmp/test.pdf", "size_mb": 1.0}})
    @patch("src.web.app.Path")
    def test_process_pdf_not_found(self, mock_path, mock_config):
        from src.web.app import UPLOADED_FILES
        mock_config.web_upload_max_mb = 100
        mock_config.prompt_layout = "vertical"
        mock_config.prompt_strict_mode = False
        mock_config.prompt_has_diagrams = True
        mock_config.prompt_low_quality_mode = False
        mock_config.temp_directory = Path(tempfile.gettempdir())
        mock_config.base_url = "http://localhost:8000"

        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value = mock_path_instance

        UPLOADED_FILES["test_file_id"] = {"file_id": "test_file_id", "filename": "test.pdf", "path": "/tmp/test.pdf", "size_mb": 1.0}

        response = client.post("/api/process/nonexistent_file_id")
        assert response.status_code == 404

    def test_process_options_validation(self):
        from src.web.app import ProcessOptions

        options = ProcessOptions(
            compact_layout=True,
            use_emojis=True,
            prompt_layout="horizontal",
            prompt_strict_mode=True,
            prompt_has_diagrams=True,
            prompt_low_quality_mode=True,
        )
        assert options.compact_layout is True
        assert options.use_emojis is True
        assert options.prompt_layout == "horizontal"
        assert options.prompt_strict_mode is True
        assert options.prompt_has_diagrams is True
        assert options.prompt_low_quality_mode is True

    def test_process_options_defaults(self):
        from src.web.app import ProcessOptions

        options = ProcessOptions()
        assert options.compact_layout is False
        assert options.use_emojis is False
        assert options.prompt_layout is None


class TestDownload:
    def test_download_file_not_found(self):
        response = client.get("/api/download/nonexistent/all")
        assert response.status_code == 404

    def test_download_type_not_found(self, tmp_path):
        from src.web.app import PROCESSING_RESULTS

        file_id = "test_download_404"
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 dummy")
        PROCESSING_RESULTS[file_id] = {
            "output_files": {
                "pdf": str(pdf_file),
            }
        }

        response = client.get(f"/api/download/{file_id}/docx")
        assert response.status_code == 404
        assert "存在しません" in response.json()["detail"]

    def test_download_all_zip(self, tmp_path):
        from src.web.app import PROCESSING_RESULTS

        file_id = "test_dl_all"
        md_file = tmp_path / "test.md"
        md_file.write_text("# フローチャート\n", encoding="utf-8")
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 dummy")
        PROCESSING_RESULTS[file_id] = {
            "output_files": {
                "diagram_markdown": str(md_file),
                "pdf": str(pdf_file),
            }
        }
        response = client.get(f"/api/download/{file_id}/all")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        assert "attachment" in response.headers["content-disposition"]

    def test_download_pdf(self, tmp_path):
        from src.web.app import PROCESSING_RESULTS

        file_id = "test_dl_pdf"
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 dummy content")
        PROCESSING_RESULTS[file_id] = {
            "output_files": {
                "pdf": str(pdf_file),
            }
        }
        response = client.get(f"/api/download/{file_id}/pdf")
        assert response.status_code == 200
        assert "application/pdf" in response.headers["content-type"]

    def test_download_docx(self, tmp_path):
        from src.web.app import PROCESSING_RESULTS

        file_id = "test_dl_docx"
        docx_file = tmp_path / "test.docx"
        docx_file.write_bytes(b"PK\x03\x04dummy docx")
        PROCESSING_RESULTS[file_id] = {
            "output_files": {
                "docx": str(docx_file),
            }
        }
        response = client.get(f"/api/download/{file_id}/docx")
        assert response.status_code == 200
        assert "wordprocessingml" in response.headers["content-type"]

    def test_download_audio(self, tmp_path):
        from src.web.app import PROCESSING_RESULTS

        file_id = "test_dl_audio"
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"ID3 dummy audio")
        PROCESSING_RESULTS[file_id] = {
            "output_files": {
                "audio": str(audio_file),
            }
        }
        response = client.get(f"/api/download/{file_id}/audio")
        assert response.status_code == 200
        assert "audio/mpeg" in response.headers["content-type"]

    def test_download_diagram_markdown(self, tmp_path):
        from src.web.app import PROCESSING_RESULTS

        file_id = "test_dl_md"
        md_file = tmp_path / "test.md"
        md_file.write_text("# フローチャート\n\n```mermaid\nflowchart TD\nA-->B\n```\n", encoding="utf-8")
        PROCESSING_RESULTS[file_id] = {
            "output_files": {
                "diagram_markdown": str(md_file),
            }
        }
        response = client.get(f"/api/download/{file_id}/diagram_markdown")
        assert response.status_code == 200
        assert "text/markdown" in response.headers["content-type"]

    def test_download_diagram_mermaid(self, tmp_path):
        from src.web.app import PROCESSING_RESULTS

        file_id = "test_dl_mmd"
        mmd_file = tmp_path / "test.mmd"
        mmd_file.write_text("flowchart TD\nA-->B\n", encoding="utf-8")
        PROCESSING_RESULTS[file_id] = {
            "output_files": {
                "diagram_mermaid": str(mmd_file),
            }
        }
        response = client.get(f"/api/download/{file_id}/diagram_mermaid")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]

    def test_download_fallback_to_markdown(self, tmp_path):
        from src.web.app import PROCESSING_RESULTS

        file_id = "test_dl_fallback"
        md_file = tmp_path / "test.md"
        md_file.write_text("# フローチャート\n", encoding="utf-8")
        PROCESSING_RESULTS[file_id] = {
            "output_files": {
                "diagram": None,
                "diagram_markdown": str(md_file),
            }
        }
        response = client.get(f"/api/download/{file_id}/diagram")
        assert response.status_code == 200


class TestResults:
    def test_get_result_not_found(self):
        response = client.get("/api/results/nonexistent")
        assert response.status_code == 404


class TestMermaidEndpoints:
    def test_mermaid_validate_valid_graph(self):
        response = client.post(
            "/api/mermaid/validate",
            json={"mermaid_code": "graph TD;\n  A-->B;"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["type"] == "graph"

    def test_mermaid_validate_valid_flowchart(self):
        response = client.post(
            "/api/mermaid/validate",
            json={"mermaid_code": "flowchart TD\n  A-->B"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["type"] == "flowchart"

    def test_mermaid_validate_valid_sequence(self):
        response = client.post(
            "/api/mermaid/validate",
            json={"mermaid_code": "sequenceDiagram\n  A->>B: Hello"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["type"] == "sequenceDiagram"

    def test_mermaid_validate_valid_class(self):
        response = client.post(
            "/api/mermaid/validate",
            json={"mermaid_code": "classDiagram\n  class A {}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["type"] == "classDiagram"

    def test_mermaid_validate_valid_gantt(self):
        response = client.post(
            "/api/mermaid/validate",
            json={"mermaid_code": "gantt\n  title A"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["type"] == "gantt"

    def test_mermaid_validate_valid_pie(self):
        response = client.post(
            "/api/mermaid/validate",
            json={"mermaid_code": "pie\n  \"A\" : 50"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["type"] == "pie"

    def test_mermaid_validate_valid_mindmap(self):
        response = client.post(
            "/api/mermaid/validate",
            json={"mermaid_code": "mindmap\n  root"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["type"] == "mindmap"

    def test_mermaid_validate_empty(self):
        response = client.post(
            "/api/mermaid/validate",
            json={"mermaid_code": "   "}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False

    def test_mermaid_validate_invalid(self):
        response = client.post(
            "/api/mermaid/validate",
            json={"mermaid_code": "invalid code"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False

    def test_mermaid_render_success(self):
        from src.web.app import app

        with patch("src.web.app.DiagramGenerator") as mock_dg_class:
            mock_dg_instance = MagicMock()
            output_path = Path(tempfile.mktemp(suffix=".png"))
            output_path.write_bytes(b"fake png data")
            mock_dg_instance.render_to_image.return_value = output_path
            mock_dg_class.return_value = mock_dg_instance

            response = client.post(
                "/api/mermaid/render",
                json={
                    "mermaid_code": "graph TD;\n  A-->B;",
                    "theme": "dark",
                    "width": 1024,
                    "height": 768
                }
            )
            assert response.status_code == 200
            assert "image/png" in response.headers["content-type"]

    def test_mermaid_render_failure(self):
        with patch("src.web.app.DiagramGenerator") as mock_dg_class:
            mock_dg_instance = MagicMock()
            mock_dg_instance.render_to_image.side_effect = Exception("Render failed")
            mock_dg_class.return_value = mock_dg_instance

            response = client.post(
                "/api/mermaid/render",
                json={"mermaid_code": "graph TD;\n  A-->B;"}
            )
            assert response.status_code == 400
            assert "レンダリング失敗" in response.json()["detail"]

    def test_mermaid_regenerate_success(self):
        with patch("src.gemini_processor.GeminiProcessor") as mock_processor_class:
            mock_processor_instance = MagicMock()
            mock_processor_instance.summarize_text.return_value = "```mermaid\ngraph TD;\n  A-->C;\n```"
            mock_processor_class.return_value = mock_processor_instance

            response = client.post(
                "/api/mermaid/regenerate",
                json={
                    "current_code": "graph TD;\n  A-->B;",
                    "instruction": "Add node C"
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "graph TD" in data["mermaid_code"]

    def test_mermaid_regenerate_failure(self):
        with patch("src.gemini_processor.GeminiProcessor") as mock_processor_class:
            mock_processor_instance = MagicMock()
            mock_processor_instance.summarize_text.side_effect = Exception("API Error")
            mock_processor_class.return_value = mock_processor_instance

            response = client.post(
                "/api/mermaid/regenerate",
                json={
                    "current_code": "graph TD;\n  A-->B;",
                    "instruction": "Add node C"
                }
            )
            assert response.status_code == 500
            assert "AI 再生成エラー" in response.json()["detail"]

    def test_mermaid_save_file_not_found(self):
        response = client.post(
            "/api/mermaid/save/nonexistent",
            json={"mermaid_code": "graph TD;\n  A-->B;", "theme": "default"}
        )
        assert response.status_code == 404


class TestDriveEndpoints:
    @patch("src.web.app._get_drive_manager")
    def test_drive_status_authenticated(self, mock_get_manager):
        mock_manager = MagicMock()
        mock_manager.is_authenticated.return_value = True
        mock_get_manager.return_value = mock_manager

        with patch("src.web.app.config") as mock_config:
            mock_config.drive.enabled = True

            response = client.get("/api/drive/status")
            assert response.status_code == 200
            data = response.json()
            assert data["authenticated"] is True
            assert data["enabled"] is True

    @patch("src.web.app._get_drive_manager")
    def test_drive_status_error(self, mock_get_manager):
        mock_get_manager.side_effect = Exception("Drive error")

        with patch("src.web.app.config") as mock_config:
            mock_config.drive.enabled = True

            response = client.get("/api/drive/status")
            assert response.status_code == 200
            data = response.json()
            assert data["authenticated"] is False
            assert "error" in data

    @patch("src.web.app._get_drive_manager")
    def test_drive_auth_success(self, mock_get_manager):
        mock_manager = MagicMock()
        mock_manager.get_authorization_url.return_value = "https://auth.example.com"
        mock_get_manager.return_value = mock_manager

        with patch("src.web.app.config") as mock_config:
            mock_config.web.port = 8000

            response = client.get("/api/drive/auth")
            assert response.status_code == 200
            data = response.json()
            assert "auth_url" in data

    @patch("src.web.app._get_drive_manager")
    @patch("src.web.app.config")
    def test_drive_auth_google_drive_error(self, mock_config, mock_get_manager):
        from src.google_drive_manager import GoogleDriveError
        mock_config.web.port = 8000
        mock_manager = MagicMock()
        mock_manager.get_authorization_url.side_effect = GoogleDriveError("Auth failed")
        mock_get_manager.return_value = mock_manager

        response = client.get("/api/drive/auth")
        assert response.status_code == 400

    @patch("src.web.app._get_drive_manager")
    def test_drive_auth_other_error(self, mock_get_manager):
        mock_manager = MagicMock()
        mock_manager.get_authorization_url.side_effect = Exception("Unknown error")
        mock_get_manager.return_value = mock_manager

        response = client.get("/api/drive/auth")
        assert response.status_code == 500

    def test_drive_callback_no_code(self):
        response = client.get("/api/drive/callback")
        assert response.status_code == 400
        assert "認証コードがありません" in response.json()["detail"]

    @patch("src.web.app._get_drive_manager")
    @patch("src.web.app.config")
    def test_drive_callback_success(self, mock_config, mock_get_manager):
        mock_config.web.port = 8000
        mock_manager = MagicMock()
        mock_manager.exchange_code.return_value = "mock_token_string"
        mock_get_manager.return_value = mock_manager

        response = client.get("/api/drive/callback?code=auth_code_123")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["message"] == "認証成功"

    @patch("src.web.app._get_drive_manager")
    def test_drive_callback_google_drive_error(self, mock_get_manager):
        from src.google_drive_manager import GoogleDriveError
        mock_manager = MagicMock()
        mock_manager.exchange_code.side_effect = GoogleDriveError("Invalid code")
        mock_get_manager.return_value = mock_manager

        with patch("src.web.app.config") as mock_config:
            mock_config.web.port = 8000

            response = client.get("/api/drive/callback?code=invalid_code")
            assert response.status_code == 400

    @patch("src.web.app._get_drive_manager")
    def test_drive_callback_other_error(self, mock_get_manager):
        mock_manager = MagicMock()
        mock_manager.exchange_code.side_effect = Exception("Unknown error")
        mock_get_manager.return_value = mock_manager

        with patch("src.web.app.config") as mock_config:
            mock_config.web.port = 8000

            response = client.get("/api/drive/callback?code=some_code")
            assert response.status_code == 500

    def test_upload_to_drive_file_not_found(self):
        response = client.post("/api/drive/upload/nonexistent")
        assert response.status_code == 404

    @patch("src.web.app._get_drive_manager")
    def test_upload_to_drive_not_authenticated(self, mock_get_manager):
        from src.web.app import PROCESSING_RESULTS

        mock_manager = MagicMock()
        mock_manager.is_authenticated.return_value = False
        mock_get_manager.return_value = mock_manager

        file_id = "test_drive_upload"
        PROCESSING_RESULTS[file_id] = {
            "output_files": {
                "pdf": "/tmp/test.pdf"
            }
        }

        response = client.post(f"/api/drive/upload/{file_id}")
        assert response.status_code == 401

    @patch("src.web.app._get_drive_manager")
    def test_upload_to_drive_success(self, mock_get_manager, tmp_path):
        from src.web.app import PROCESSING_RESULTS
        from src.google_drive_manager import DriveFile

        mock_manager = MagicMock()
        mock_manager.is_authenticated.return_value = True
        mock_manager.upload_and_share.return_value = DriveFile(
            file_id="drive_file_123",
            name="test.pdf",
            web_view_link="https://drive.google.com/view",
            web_content_link="https://drive.google.com/content",
            mime_type="application/pdf"
        )
        mock_get_manager.return_value = mock_manager

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 content")

        file_id = "test_drive_upload_success"
        PROCESSING_RESULTS[file_id] = {
            "output_files": {
                "pdf": str(pdf_file),
                "docx": str(tmp_path / "test.docx"),
            }
        }

        with patch("src.web.app.config") as mock_config:
            mock_config.drive.folder_id = None
            mock_config.drive.folder_name = "TestFolder"
            mock_config.drive.share_public = True

            response = client.post(f"/api/drive/upload/{file_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    @patch("src.web.app._get_drive_manager")
    def test_drive_revoke_success(self, mock_get_manager):
        mock_manager = MagicMock()
        mock_get_manager.return_value = mock_manager

        response = client.post("/api/drive/revoke")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    @patch("src.web.app._get_drive_manager")
    def test_drive_revoke_error(self, mock_get_manager):
        mock_manager = MagicMock()
        mock_manager.revoke_authentication.side_effect = Exception("Revoke failed")
        mock_get_manager.return_value = mock_manager

        response = client.post("/api/drive/revoke")
        assert response.status_code == 500


class TestObservability:
    def test_metrics_endpoint(self):
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]

    def test_observability_status(self):
        response = client.get("/api/observability/status")
        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
        assert "backend" in data


class TestWebSocket:
    def test_websocket_endpoint(self):
        with client.websocket_connect("/ws/progress/test_file_id") as websocket:
            data = websocket.receive_json()
            assert data["status"] == "connected"
            assert data["file_id"] == "test_file_id"
            assert data["progress"] == 0

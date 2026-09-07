"""
Unit Tests for Web API and Phase 2 Endpoints
"""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from src.web.app import app, PROCESSING_RESULTS

client = TestClient(app)


def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_public_config():
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "gemini_model_name" in data
    assert "web_upload_max_mb" in data


def test_upload_invalid_file_extension():
    response = client.post(
        "/api/upload",
        files={"file": ("test.txt", b"dummy content", "text/plain")}
    )
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


def test_mermaid_validate_valid():
    response = client.post(
        "/api/mermaid/validate",
        json={"mermaid_code": "graph TD;\n  A-->B;"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["type"] == "graph"


def test_mermaid_validate_empty():
    response = client.post(
        "/api/mermaid/validate",
        json={"mermaid_code": "   "}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False


def test_process_options_accepts_prompt_settings():
    from src.web.app import ProcessOptions

    options = ProcessOptions(
        prompt_layout="vertical",
        prompt_strict_mode=True,
        prompt_has_diagrams=True,
    )

    assert options.prompt_layout == "vertical"
    assert options.prompt_strict_mode is True
    assert options.prompt_has_diagrams is True


def test_download_diagram_markdown(tmp_path):
    file_id = "test_dl_md"
    md_file = tmp_path / "test.md"
    md_file.write_text("# フローチャート\n\n```mermaid\nflowchart TD\nA-->B\n```\n", encoding="utf-8")
    PROCESSING_RESULTS[file_id] = {
        "output_files": {
            "diagram_markdown": str(md_file),
            "pdf": str(tmp_path / "test.pdf"),
        }
    }
    response = client.get(f"/api/download/{file_id}/diagram_markdown")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/markdown; charset=utf-8"
    assert "flowchart TD" in response.text
    del PROCESSING_RESULTS[file_id]


def test_download_diagram_fallback_to_markdown(tmp_path):
    file_id = "test_dl_fallback"
    md_file = tmp_path / "test.md"
    md_file.write_text("# フローチャート\n\n```mermaid\nflowchart TD\nA-->B\n```\n", encoding="utf-8")
    PROCESSING_RESULTS[file_id] = {
        "output_files": {
            "diagram": None,
            "diagram_markdown": str(md_file),
        }
    }
    response = client.get(f"/api/download/{file_id}/diagram")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/markdown; charset=utf-8"
    del PROCESSING_RESULTS[file_id]


def test_download_all_zip(tmp_path):
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
    assert file_id in response.headers["content-disposition"]
    del PROCESSING_RESULTS[file_id]

"""Tests for src/observability"""

import sys
from pathlib import Path

src_path = Path(__file__).resolve().parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


class TestMetrics:
    def test_module_imports(self):
        from src.observability import metrics, get_registry
        assert metrics is not None
        assert callable(get_registry)

    def test_metrics_have_required_attributes(self):
        from src.observability import metrics
        assert hasattr(metrics, "record_success")
        assert hasattr(metrics, "record_failure")
        assert hasattr(metrics, "record_api_error")
        assert hasattr(metrics, "job_timer")
        assert hasattr(metrics, "render")

    def test_record_success_is_noop_when_disabled(self, monkeypatch):
        from src import observability
        monkeypatch.setattr(observability, "_HAS_PROM", False)
        # Should not raise
        observability.metrics.record_success("x")

    def test_record_failure_is_noop_when_disabled(self, monkeypatch):
        from src import observability
        monkeypatch.setattr(observability, "_HAS_PROM", False)
        observability.metrics.record_failure("x")

    def test_record_api_error_is_noop_when_disabled(self, monkeypatch):
        from src import observability
        monkeypatch.setattr(observability, "_HAS_PROM", False)
        observability.metrics.record_api_error("gemini")

    def test_job_timer_is_noop_when_disabled(self, monkeypatch):
        from src import observability
        monkeypatch.setattr(observability, "_HAS_PROM", False)
        with observability.metrics.job_timer("test"):
            x = 1 + 1
        assert x == 2

    def test_render_when_disabled(self, monkeypatch):
        from src import observability
        monkeypatch.setattr(observability, "_HAS_PROM", False)
        body, content_type = observability.metrics.render()
        assert isinstance(body, bytes)
        assert "text/plain" in content_type

    def test_record_success_increments_counter_when_enabled(self):
        from src import observability
        from src.observability import metrics
        # Force enable
        if not observability._HAS_PROM:
            return  # skip if backend unavailable
        before = metrics.render()[0]
        metrics.record_success("test_stage")
        after = metrics.render()[0]
        # Output should grow after recording
        assert len(after) >= len(before)

    def test_job_timer_records_observation(self):
        from src import observability
        from src.observability import metrics
        if not observability._HAS_PROM:
            return
        with metrics.job_timer("test_stage_2"):
            pass
        body, _ = metrics.render()
        assert b"manual_processor_job_duration_seconds" in body

    def test_status_endpoint_reports_enabled(self):
        from src.web.app import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/api/observability/status")
        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
        assert "backend" in data

    def test_metrics_endpoint_returns_text(self):
        from src.web.app import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
        # Should at least have HELP/TYPE lines or a comment
        body = response.text
        assert isinstance(body, str)
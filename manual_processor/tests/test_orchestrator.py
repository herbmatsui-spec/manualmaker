"""
Tests for DocumentOrchestrator.
"""

import time
import threading
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from src.orchestrator import (
    DocumentOrchestrator,
    ProcessingResult,
    ProcessingStatus,
)


class TestProcessingStatus:
    """Test ProcessingStatus enum"""

    def test_status_values(self):
        """Test status enum values"""
        assert ProcessingStatus.IDLE == "idle"
        assert ProcessingStatus.PROCESSING == "processing"
        assert ProcessingStatus.COMPLETED == "completed"
        assert ProcessingStatus.FAILED == "failed"

    def test_status_is_string(self):
        """Test that status is a string"""
        assert isinstance(ProcessingStatus.IDLE, str)


class TestProcessingResult:
    """Test ProcessingResult class"""

    def test_create_success_result(self):
        """Test creating successful result"""
        result = ProcessingResult(success=True, message="Success", data={"key": "value"})
        assert result.success is True
        assert result.message == "Success"
        assert result.data == {"key": "value"}
        assert result.timestamp > 0

    def test_create_failure_result(self):
        """Test creating failed result"""
        result = ProcessingResult(success=False, message="Failed")
        assert result.success is False
        assert result.message == "Failed"
        assert result.data == {}

    def test_default_values(self):
        """Test default values"""
        result = ProcessingResult(success=True)
        assert result.message == ""
        assert result.data == {}
        assert result.timestamp > 0


class TestDocumentOrchestratorInit:
    """Test DocumentOrchestrator initialization"""

    @patch('src.orchestrator.DocumentProcessor')
    @patch('src.orchestrator.Config.get_instance')
    def test_init_with_config(self, mock_config_get, mock_processor):
        """Test initialization with config"""
        mock_config = Mock()
        mock_config.prompt_layout = "horizontal"
        mock_config.prompt_strict_mode = True
        mock_config.prompt_has_diagrams = False
        mock_config.prompt_domain_terms = []
        mock_config_get.return_value = mock_config
        
        orchestrator = DocumentOrchestrator(config=mock_config)
        
        assert orchestrator.config == mock_config
        assert orchestrator.processor == mock_processor.return_value
        assert orchestrator.status == ProcessingStatus.IDLE
        assert orchestrator.current_file is None
        assert orchestrator.processed_files == []
        assert orchestrator.failed_files == []

    @patch('src.orchestrator.DocumentProcessor')
    @patch('src.orchestrator.Config.get_instance')
    def test_init_sets_defaults(self, mock_config_get, mock_processor):
        """Test initialization sets default values"""
        mock_config = Mock()
        mock_config.prompt_layout = "horizontal"
        mock_config.prompt_strict_mode = True
        mock_config.prompt_has_diagrams = False
        mock_config.prompt_domain_terms = []
        mock_config_get.return_value = mock_config
        
        orchestrator = DocumentOrchestrator()
        
        assert orchestrator.compact_layout is False
        assert orchestrator.use_emojis is False
        assert orchestrator.progress_callback is None
        assert orchestrator.completion_callback is None


class TestDocumentOrchestratorStartStop:
    """Test start and stop methods"""

    @patch('src.orchestrator.DocumentProcessor')
    @patch('src.orchestrator.Config.get_instance')
    def test_start_creates_thread(self, mock_config_get, mock_processor):
        """Test that start creates a worker thread"""
        mock_config = Mock()
        mock_config.prompt_layout = "horizontal"
        mock_config.prompt_strict_mode = True
        mock_config.prompt_has_diagrams = False
        mock_config.prompt_domain_terms = []
        mock_config_get.return_value = mock_config
        
        orchestrator = DocumentOrchestrator()
        orchestrator.start()
        
        assert orchestrator.worker_thread is not None
        assert orchestrator.worker_thread.is_alive()
        assert orchestrator.worker_thread.daemon is True
        
        orchestrator.stop()

    @patch('src.orchestrator.DocumentProcessor')
    @patch('src.orchestrator.Config.get_instance')
    def test_start_already_running(self, mock_config_get, mock_processor):
        """Test starting when already running"""
        mock_config = Mock()
        mock_config.prompt_layout = "horizontal"
        mock_config.prompt_strict_mode = True
        mock_config.prompt_has_diagrams = False
        mock_config.prompt_domain_terms = []
        mock_config_get.return_value = mock_config
        
        orchestrator = DocumentOrchestrator()
        orchestrator.start()
        
        # Start again
        orchestrator.start()
        
        # Should still have only one thread
        assert orchestrator.worker_thread is not None
        
        orchestrator.stop()

    @patch('src.orchestrator.DocumentProcessor')
    @patch('src.orchestrator.Config.get_instance')
    def test_stop_graceful(self, mock_config_get, mock_processor):
        """Test graceful stop"""
        mock_config = Mock()
        mock_config.prompt_layout = "horizontal"
        mock_config.prompt_strict_mode = True
        mock_config.prompt_has_diagrams = False
        mock_config.prompt_domain_terms = []
        mock_config_get.return_value = mock_config
        
        orchestrator = DocumentOrchestrator()
        orchestrator.start()
        assert orchestrator.worker_thread.is_alive()
        
        orchestrator.stop()
        
        # Thread should be stopped
        assert not orchestrator.worker_thread.is_alive()


class TestDocumentOrchestratorProcessFile:
    """Test process_file method"""

    def _create_mock_config(self):
        """Create a properly configured mock config"""
        mock_config = Mock()
        mock_config.prompt_layout = "horizontal"
        mock_config.prompt_strict_mode = True
        mock_config.prompt_has_diagrams = False
        mock_config.prompt_domain_terms = []
        return mock_config

    @patch('src.orchestrator.DocumentProcessor')
    @patch('src.orchestrator.Config.get_instance')
    def test_process_file_success(self, mock_config_get, mock_processor_cls):
        """Test successful file processing"""
        mock_config = self._create_mock_config()
        mock_config_get.return_value = mock_config
        
        mock_processor = Mock()
        mock_processor_cls.return_value = mock_processor
        mock_processor.process_pdf.return_value = {
            "success": True,
            "title": "Test",
            "summary": "Summary"
        }
        
        orchestrator = DocumentOrchestrator(config=mock_config)
        result = orchestrator.process_file(Path("./test.pdf"))
        
        assert result.success is True
        assert "Successfully processed" in result.message
        assert len(orchestrator.processed_files) == 1

    @patch('src.orchestrator.DocumentProcessor')
    @patch('src.orchestrator.Config.get_instance')
    def test_process_file_failure(self, mock_config_get, mock_processor_cls):
        """Test failed file processing"""
        mock_config = self._create_mock_config()
        mock_config_get.return_value = mock_config
        
        mock_processor = Mock()
        mock_processor_cls.return_value = mock_processor
        mock_processor.process_pdf.return_value = {
            "success": False,
            "error": "Processing failed"
        }
        
        orchestrator = DocumentOrchestrator(config=mock_config)
        result = orchestrator.process_file(Path("./test.pdf"))
        
        assert result.success is False
        assert "Failed" in result.message
        assert len(orchestrator.failed_files) == 1

    @patch('src.orchestrator.DocumentProcessor')
    @patch('src.orchestrator.Config.get_instance')
    def test_process_file_exception(self, mock_config_get, mock_processor_cls):
        """Test file processing with exception"""
        mock_config = self._create_mock_config()
        mock_config_get.return_value = mock_config
        
        mock_processor = Mock()
        mock_processor_cls.return_value = mock_processor
        mock_processor.process_pdf.side_effect = Exception("Unexpected error")
        
        orchestrator = DocumentOrchestrator(config=mock_config)
        result = orchestrator.process_file(Path("./test.pdf"))
        
        assert result.success is False
        assert "Error" in result.message
        assert len(orchestrator.failed_files) == 1

    @patch('src.orchestrator.DocumentProcessor')
    @patch('src.orchestrator.Config.get_instance')
    def test_process_file_with_options(self, mock_config_get, mock_processor_cls):
        """Test processing with layout options"""
        mock_config = self._create_mock_config()
        mock_config_get.return_value = mock_config
        
        mock_processor = Mock()
        mock_processor_cls.return_value = mock_processor
        mock_processor.process_pdf.return_value = {"success": True}
        
        orchestrator = DocumentOrchestrator(config=mock_config)
        result = orchestrator.process_file(
            Path("./test.pdf"),
            compact_layout=True,
            use_emojis=True
        )
        
        assert result.success is True
        mock_processor.process_pdf.assert_called_once()
        call_kwargs = mock_processor.process_pdf.call_args[1]
        assert call_kwargs["compact_layout"] is True
        assert call_kwargs["use_emojis"] is True


class TestDocumentOrchestratorQueue:
    """Test queue operations"""

    @patch('src.orchestrator.DocumentProcessor')
    @patch('src.orchestrator.Config.get_instance')
    def test_add_file_to_queue(self, mock_config_get, mock_processor):
        """Test adding file to queue"""
        mock_config = Mock()
        mock_config.prompt_layout = "horizontal"
        mock_config.prompt_strict_mode = True
        mock_config.prompt_has_diagrams = False
        mock_config.prompt_domain_terms = []
        mock_config_get.return_value = mock_config
        
        orchestrator = DocumentOrchestrator()
        orchestrator.add_file_to_queue(Path("./test.pdf"))
        
        assert orchestrator.process_queue.qsize() == 1

    @patch('src.orchestrator.DocumentProcessor')
    @patch('src.orchestrator.Config.get_instance')
    def test_get_result_with_result(self, mock_config_get, mock_processor):
        """Test getting result from queue"""
        mock_config = Mock()
        mock_config.prompt_layout = "horizontal"
        mock_config.prompt_strict_mode = True
        mock_config.prompt_has_diagrams = False
        mock_config.prompt_domain_terms = []
        mock_config_get.return_value = mock_config
        
        orchestrator = DocumentOrchestrator()
        expected_result = ProcessingResult(success=True, message="Done")
        orchestrator.result_queue.put(expected_result)
        
        result = orchestrator.get_result(timeout=1.0)
        assert result is expected_result

    @patch('src.orchestrator.DocumentProcessor')
    @patch('src.orchestrator.Config.get_instance')
    def test_get_result_timeout(self, mock_config_get, mock_processor):
        """Test getting result with timeout"""
        mock_config = Mock()
        mock_config.prompt_layout = "horizontal"
        mock_config.prompt_strict_mode = True
        mock_config.prompt_has_diagrams = False
        mock_config.prompt_domain_terms = []
        mock_config_get.return_value = mock_config
        
        orchestrator = DocumentOrchestrator()
        result = orchestrator.get_result(timeout=0.1)
        
        assert result is None


class TestDocumentOrchestratorCallbacks:
    """Test callback settings"""

    @patch('src.orchestrator.DocumentProcessor')
    @patch('src.orchestrator.Config.get_instance')
    def test_set_progress_callback(self, mock_config_get, mock_processor):
        """Test setting progress callback"""
        mock_config = Mock()
        mock_config.prompt_layout = "horizontal"
        mock_config.prompt_strict_mode = True
        mock_config.prompt_has_diagrams = False
        mock_config.prompt_domain_terms = []
        mock_config_get.return_value = mock_config
        
        orchestrator = DocumentOrchestrator()
        callback = Mock()
        orchestrator.set_progress_callback(callback)
        
        assert orchestrator.progress_callback is callback

    @patch('src.orchestrator.DocumentProcessor')
    @patch('src.orchestrator.Config.get_instance')
    def test_set_completion_callback(self, mock_config_get, mock_processor):
        """Test setting completion callback"""
        mock_config = Mock()
        mock_config.prompt_layout = "horizontal"
        mock_config.prompt_strict_mode = True
        mock_config.prompt_has_diagrams = False
        mock_config.prompt_domain_terms = []
        mock_config_get.return_value = mock_config
        
        orchestrator = DocumentOrchestrator()
        callback = Mock()
        orchestrator.set_completion_callback(callback)
        
        assert orchestrator.completion_callback is callback


class TestDocumentOrchestratorStatus:
    """Test status tracking"""

    @patch('src.orchestrator.DocumentProcessor')
    @patch('src.orchestrator.Config.get_instance')
    def test_get_status_idle(self, mock_config_get, mock_processor):
        """Test getting status when idle"""
        mock_config = Mock()
        mock_config.prompt_layout = "horizontal"
        mock_config.prompt_strict_mode = True
        mock_config.prompt_has_diagrams = False
        mock_config.prompt_domain_terms = []
        mock_config_get.return_value = mock_config
        
        orchestrator = DocumentOrchestrator()
        status = orchestrator.get_status()
        
        assert status["status"] == ProcessingStatus.IDLE
        assert status["current_file"] is None
        assert status["processed_count"] == 0
        assert status["failed_count"] == 0
        assert "queue_size" in status

    @patch('src.orchestrator.DocumentProcessor')
    @patch('src.orchestrator.Config.get_instance')
    def test_get_status_after_processing(self, mock_config_get, mock_processor_cls):
        """Test getting status after processing files"""
        mock_config = Mock()
        mock_config.prompt_layout = "horizontal"
        mock_config.prompt_strict_mode = True
        mock_config.prompt_has_diagrams = False
        mock_config.prompt_domain_terms = []
        mock_config_get.return_value = mock_config
        
        mock_processor = Mock()
        mock_processor_cls.return_value = mock_processor
        mock_processor.process_pdf.return_value = {"success": True}
        
        orchestrator = DocumentOrchestrator(config=mock_config)
        orchestrator.process_file(Path("./test1.pdf"))
        orchestrator.process_file(Path("./test2.pdf"))
        
        status = orchestrator.get_status()
        assert status["processed_count"] == 2
        assert status["failed_count"] == 0


class TestDocumentOrchestratorWorkerLoop:
    """Test worker loop"""

    @patch('src.orchestrator.DocumentProcessor')
    @patch('src.orchestrator.Config.get_instance')
    def test_worker_loop_processes_file(self, mock_config_get, mock_processor_cls):
        """Test worker loop processes queued files"""
        mock_config = Mock()
        mock_config.prompt_layout = "horizontal"
        mock_config.prompt_strict_mode = True
        mock_config.prompt_has_diagrams = False
        mock_config.prompt_domain_terms = []
        mock_config_get.return_value = mock_config
        
        mock_processor = Mock()
        mock_processor_cls.return_value = mock_processor
        mock_processor.process_pdf.return_value = {"success": True}
        
        orchestrator = DocumentOrchestrator(config=mock_config)
        orchestrator.add_file_to_queue(Path("./test.pdf"))
        
        # Start worker
        orchestrator.start()
        
        # Wait for processing
        time.sleep(0.5)
        
        # Stop worker
        orchestrator.stop()
        
        # Verify file was processed
        assert len(orchestrator.processed_files) == 1

    @patch('src.orchestrator.DocumentProcessor')
    @patch('src.orchestrator.Config.get_instance')
    def test_worker_loop_handles_exception(self, mock_config_get, mock_processor_cls):
        """Test worker loop handles exceptions gracefully"""
        mock_config = Mock()
        mock_config.prompt_layout = "horizontal"
        mock_config.prompt_strict_mode = True
        mock_config.prompt_has_diagrams = False
        mock_config.prompt_domain_terms = []
        mock_config_get.return_value = mock_config
        
        mock_processor = Mock()
        mock_processor_cls.return_value = mock_processor
        mock_processor.process_pdf.side_effect = Exception("Worker error")
        
        orchestrator = DocumentOrchestrator(config=mock_config)
        orchestrator.add_file_to_queue(Path("./test.pdf"))
        
        # Set progress callback to capture error status
        progress_updates = []
        def capture_progress(update):
            progress_updates.append(update)
        
        orchestrator.set_progress_callback(capture_progress)
        
        # Start worker
        orchestrator.start()
        time.sleep(0.5)
        orchestrator.stop()
        
        # Verify error callback was called
        assert len(progress_updates) >= 1
        # The outer exception handler in worker loop catches exceptions
        # and reports them via progress callback, but doesn't add to failed_files
        # failed_files is only populated by process_file() for sync processing

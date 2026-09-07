"""Tests for src/batch_processor.py"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
from queue import PriorityQueue

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


class TestBatchJob:
    """Tests for BatchJob dataclass"""

    def test_batch_job_priority_ordering(self):
        from batch_processor import BatchJob

        low = BatchJob(priority=10, file_path=Path("/a.pdf"))
        high = BatchJob(priority=1, file_path=Path("/b.pdf"))
        assert high < low

    def test_batch_job_same_priority_equal(self):
        from batch_processor import BatchJob

        t = time.time()
        a = BatchJob(priority=5, file_path=Path("/a.pdf"), added_time=t)
        b = BatchJob(priority=5, file_path=Path("/b.pdf"), added_time=t + 0.001)
        assert not (a < b)
        assert not (b < a)


class TestBatchProcessorInit:
    """Tests for BatchProcessor.__init__"""

    def test_init_with_processor_only(self):
        from batch_processor import BatchProcessor

        class SimpleProc:
            pass
        proc = SimpleProc()
        bp = BatchProcessor(proc)
        assert bp.processor is proc
        assert bp.prompt_builder is None
        assert isinstance(bp.queue, PriorityQueue)

    def test_init_with_prompt_builder(self):
        from batch_processor import BatchProcessor

        proc = MagicMock()
        pb = MagicMock()
        bp = BatchProcessor(proc, prompt_builder=pb)
        assert bp.processor is proc
        assert bp.prompt_builder is pb


class TestGetPromptContext:
    """Tests for get_prompt_context()"""

    def test_returns_none_when_no_prompt_builder(self):
        from batch_processor import BatchProcessor

        class SimpleProc:
            pass
        bp = BatchProcessor(SimpleProc())
        assert bp.get_prompt_context() is None

    def test_returns_context_when_prompt_builder_exists(self):
        from batch_processor import BatchProcessor

        pb = MagicMock()
        pb.build_processing_context.return_value = "test context"
        bp = BatchProcessor(MagicMock(), prompt_builder=pb)
        assert bp.get_prompt_context() == "test context"
        pb.build_processing_context.assert_called_once()


class TestAddFile:
    """Tests for add_file()"""

    def test_add_file_default_priority(self):
        from batch_processor import BatchProcessor

        bp = BatchProcessor(MagicMock())
        bp.add_file(Path("/test.pdf"))
        assert bp.queue.qsize() == 1
        job = bp.queue.get()
        assert job.file_path == Path("/test.pdf")
        assert job.priority == 10

    def test_add_file_custom_priority(self):
        from batch_processor import BatchProcessor

        bp = BatchProcessor(MagicMock())
        bp.add_file(Path("/test.pdf"), priority=5)
        job = bp.queue.get()
        assert job.priority == 5


class TestAddDirectory:
    """Tests for add_directory()"""

    def test_add_directory_not_found_raises(self):
        from batch_processor import BatchProcessor

        bp = BatchProcessor(MagicMock())
        with pytest.raises(FileNotFoundError):
            bp.add_directory(Path("/nonexistent"))

    def test_add_directory_not_a_directory_raises(self, tmp_path):
        from batch_processor import BatchProcessor

        bp = BatchProcessor(MagicMock())
        with pytest.raises(FileNotFoundError):
            bp.add_directory(tmp_path / "file.pdf")

    def test_add_directory_finds_pdf_files(self, tmp_path):
        from batch_processor import BatchProcessor

        (tmp_path / "a.pdf").touch()
        (tmp_path / "b.PDF").touch()
        (tmp_path / "c.txt").touch()
        bp = BatchProcessor(MagicMock())
        count = bp.add_directory(tmp_path)
        assert count == 2
        assert bp.queue.qsize() == 2

    def test_add_directory_with_custom_extensions(self, tmp_path):
        from batch_processor import BatchProcessor

        (tmp_path / "a.pdf").touch()
        (tmp_path / "b.txt").touch()
        bp = BatchProcessor(MagicMock())
        count = bp.add_directory(tmp_path, extensions=['.txt'])
        assert count == 1

    def test_add_directory_empty_returns_zero(self, tmp_path):
        from batch_processor import BatchProcessor

        bp = BatchProcessor(MagicMock())
        count = bp.add_directory(tmp_path)
        assert count == 0


class TestProcessAll:
    """Tests for process_all()"""

    def test_process_all_empty_queue(self):
        from batch_processor import BatchProcessor

        bp = BatchProcessor(MagicMock())
        result = bp.process_all()
        assert result["total_jobs"] == 0
        assert result["processed"] == 0
        assert result["failed"] == 0

    def test_process_all_normal(self):
        from batch_processor import BatchProcessor

        proc = MagicMock()
        proc.process_pdf.return_value = {"success": True, "file": "a.pdf"}
        bp = BatchProcessor(proc)
        bp.add_file(Path("/a.pdf"))
        bp.add_file(Path("/b.pdf"))

        result = bp.process_all()
        assert result["total_jobs"] == 2
        assert result["processed"] == 2
        assert result["failed"] == 0
        assert result["successful"] == 2
        assert len(result["results"]) == 2

    def test_process_all_with_failures(self):
        from batch_processor import BatchProcessor

        proc = MagicMock()
        proc.process_pdf.side_effect = [RuntimeError("fail"), {"success": True}]
        bp = BatchProcessor(proc)
        bp.add_file(Path("/a.pdf"))
        bp.add_file(Path("/b.pdf"))

        result = bp.process_all()
        assert result["processed"] == 2
        assert result["failed"] == 1
        assert result["successful"] == 1

    def test_process_all_cancelled_before_loop(self):
        from batch_processor import BatchProcessor
        from src.progress_manager import CancellationToken

        proc = MagicMock()
        proc.process_pdf.return_value = {"success": True}
        cancel_token = CancellationToken()
        cancel_token.cancel()

        bp = BatchProcessor(proc)
        bp.add_file(Path("/a.pdf"))
        bp.add_file(Path("/b.pdf"))

        result = bp.process_all(cancel_token=cancel_token)
        assert result["processed"] == 0

    def test_process_all_with_progress_tracker(self):
        from batch_processor import BatchProcessor
        from src.progress_manager import ProgressTracker

        proc = MagicMock()
        proc.process_pdf.return_value = {"success": True}
        tracker = MagicMock(spec=ProgressTracker)

        bp = BatchProcessor(proc)
        bp.add_file(Path("/a.pdf"))

        result = bp.process_all(progress_tracker=tracker)
        assert result["processed"] == 1
        tracker.update.assert_called()

    def test_process_all_non_success_result_counts_failure(self):
        from batch_processor import BatchProcessor

        proc = MagicMock()
        proc.process_pdf.return_value = {"success": False, "error": "some error"}
        bp = BatchProcessor(proc)
        bp.add_file(Path("/a.pdf"))

        result = bp.process_all()
        assert result["failed"] == 1
        assert result["successful"] == 0

    def test_process_all_with_prompt_context(self):
        from batch_processor import BatchProcessor

        pb = MagicMock()
        pb.build_processing_context.return_value = "shared context"
        proc = MagicMock()
        proc.process_pdf.return_value = {"success": True}

        bp = BatchProcessor(proc, prompt_builder=pb)
        bp.add_file(Path("/a.pdf"))

        result = bp.process_all()
        assert result["processed"] == 1

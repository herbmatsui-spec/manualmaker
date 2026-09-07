"""
Tests for progress_manager module (Step 17)
Target coverage: 95%
"""

import pytest
import threading
import time
from unittest.mock import Mock, MagicMock, patch

from src.progress_manager import (
    CancellationToken,
    OperationCancelledError,
    ProgressTracker,
    ProgressStatus,
)


class TestCancellationToken:
    """Test CancellationToken class"""

    def test_init_not_cancelled(self):
        token = CancellationToken()
        assert not token.is_cancelled

    def test_cancel_sets_flag(self):
        token = CancellationToken()
        token.cancel()
        assert token.is_cancelled

    def test_cancel_only_once(self):
        token = CancellationToken()
        token.cancel()
        token.cancel()
        assert token.is_cancelled

    def test_throw_if_cancelled_when_not_cancelled(self):
        token = CancellationToken()
        token.throw_if_cancelled()

    def test_throw_if_cancelled_raises_when_cancelled(self):
        token = CancellationToken()
        token.cancel()
        with pytest.raises(OperationCancelledError):
            token.throw_if_cancelled()

    def test_throw_if_cancelled_error_message(self):
        token = CancellationToken()
        token.cancel()
        with pytest.raises(OperationCancelledError) as exc_info:
            token.throw_if_cancelled()
        assert "cancelled by user" in str(exc_info.value)

    def test_throwIfCancelled_alias(self):
        token = CancellationToken()
        token.cancel()
        with pytest.raises(OperationCancelledError):
            token.throwIfCancelled()

    def test_thread_safety(self):
        token = CancellationToken()

        def cancel_after_delay():
            time.sleep(0.05)
            token.cancel()

        thread = threading.Thread(target=cancel_after_delay)
        thread.start()

        for _ in range(20):
            if token.is_cancelled:
                break
            time.sleep(0.01)

        assert token.is_cancelled
        thread.join()


class TestProgressStatus:
    """Test ProgressStatus dataclass"""

    def test_init_default_timestamp(self):
        status = ProgressStatus(stage="test", percentage=50.0, message="testing")
        assert status.timestamp > 0

    def test_init_with_details(self):
        status = ProgressStatus(
            stage="test",
            percentage=50.0,
            message="testing",
            details={"key": "value"},
        )
        assert status.details == {"key": "value"}

    def test_init_with_custom_timestamp(self):
        ts = 1234567890.0
        status = ProgressStatus(
            stage="test",
            percentage=50.0,
            message="testing",
            timestamp=ts,
        )
        assert status.timestamp == ts


class TestProgressTracker:
    """Test ProgressTracker class"""

    def test_init_without_callback(self):
        tracker = ProgressTracker()
        assert tracker.callback is None
        assert tracker.current_status is None

    def test_init_with_callback(self):
        callback = Mock()
        tracker = ProgressTracker(callback=callback)
        assert tracker.callback is callback

    def test_update_sets_status(self):
        tracker = ProgressTracker()
        tracker.update("test", 50.0, "testing")
        assert tracker.current_status is not None
        assert tracker.current_status.stage == "test"
        assert tracker.current_status.percentage == 50.0
        assert tracker.current_status.message == "testing"

    def test_update_calls_callback(self):
        callback = Mock()
        tracker = ProgressTracker(callback=callback)
        tracker.update("test", 50.0, "testing")
        callback.assert_called_once()
        status = callback.call_args[0][0]
        assert status.stage == "test"

    def test_update_without_callback_no_error(self):
        tracker = ProgressTracker()
        tracker.update("test", 50.0, "testing")

    def test_update_clips_percentage_to_valid_range(self):
        tracker = ProgressTracker()

        tracker.update("test", -10.0, "too low")
        assert tracker.current_status.percentage == 0.0

        tracker.update("test", 150.0, "too high")
        assert tracker.current_status.percentage == 100.0

        tracker.update("test", 50.0, "just right")
        assert tracker.current_status.percentage == 50.0

    def test_update_with_details(self):
        tracker = ProgressTracker()
        tracker.update("test", 50.0, "testing", details={"key": "value"})
        assert tracker.current_status.details == {"key": "value"}

    def test_update_details_defaults_to_empty_dict(self):
        tracker = ProgressTracker()
        tracker.update("test", 50.0, "testing")
        assert tracker.current_status.details == {}

    def test_update_callback_exception_handled(self):
        callback = Mock(side_effect=Exception("Callback error"))
        tracker = ProgressTracker(callback=callback)

        tracker.update("test", 50.0, "testing")
        assert tracker.current_status is not None

    def test_update_empty_message(self):
        tracker = ProgressTracker()
        tracker.update("test", 50.0, "")
        assert tracker.current_status.message == ""

    def test_update_empty_stage(self):
        tracker = ProgressTracker()
        tracker.update("", 50.0, "testing")
        assert tracker.current_status.stage == ""

    def test_multiple_updates(self):
        callback = Mock()
        tracker = ProgressTracker(callback=callback)

        tracker.update("stage1", 25.0, "step 1")
        tracker.update("stage2", 50.0, "step 2")
        tracker.update("stage3", 75.0, "step 3")

        assert tracker.current_status.percentage == 75.0
        assert tracker.current_status.stage == "stage3"
        assert callback.call_count == 3

    def test_update_with_none_details(self):
        tracker = ProgressTracker()
        tracker.update("test", 50.0, "testing", details=None)
        assert tracker.current_status.details == {}

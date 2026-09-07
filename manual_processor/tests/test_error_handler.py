"""
Tests for error handler module.
"""

import logging
from unittest.mock import Mock, patch

import pytest

from src.error_handler import (
    handle_error,
    wrap_operation,
    set_gui_error_callback,
)


class TestHandleError:
    """Test error handling function"""

    def setup_method(self):
        """Reset GUI callback before each test"""
        set_gui_error_callback(None)

    @patch('src.error_handler.log_exception')
    def test_handle_error_critical_exception(self, mock_log_exception):
        """Test handling critical exceptions (returns False)"""
        error = FileNotFoundError("File not found")
        result = handle_error(error, "test context", show_user_notification=False)
        assert result is False
        mock_log_exception.assert_called_once()

    @patch('src.error_handler.log_exception')
    def test_handle_error_non_critical_exception(self, mock_log_exception):
        """Test handling non-critical exceptions (returns True)"""
        error = ValueError("Invalid value")
        result = handle_error(error, "test context", show_user_notification=False)
        assert result is True
        mock_log_exception.assert_called_once()

    @patch('src.error_handler.log_exception')
    def test_handle_error_with_gui_callback(self, mock_log_exception):
        """Test error handling with GUI callback"""
        callback = Mock()
        set_gui_error_callback(callback)

        error = RuntimeError("Test error")
        result = handle_error(error, "test context", show_user_notification=True)

        # Should call GUI callback
        callback.assert_called_once()
        assert "Test error" in callback.call_args[0][0]

    @patch('src.error_handler.log_exception')
    def test_handle_error_no_callback(self, mock_log_exception):
        """Test error handling without GUI callback"""
        set_gui_error_callback(None)

        error = RuntimeError("Test error")
        result = handle_error(error, "test context", show_user_notification=True)

        # Should not crash, should log
        mock_log_exception.assert_called_once()

    @patch('src.error_handler.log_exception')
    def test_handle_error_no_notification(self, mock_log_exception):
        """Test error handling with notifications disabled"""
        error = RuntimeError("Test error")
        result = handle_error(error, "test context", show_user_notification=False)

        # Should log but not notify
        mock_log_exception.assert_called_once()

    @patch('src.error_handler.log_exception')
    def test_handle_error_gui_callback_exception(self, mock_log_exception):
        """Test GUI callback exception handling"""
        callback = Mock(side_effect=Exception("Callback failed"))
        set_gui_error_callback(callback)

        error = RuntimeError("Test error")
        # Should not raise, should handle gracefully
        result = handle_error(error, "test context", show_user_notification=True)

        # Should still log the original error
        mock_log_exception.assert_called_once()


class TestWrapOperation:
    """Test operation wrapper"""

    @patch('src.error_handler.handle_error')
    def test_wrap_operation_success(self, mock_handle_error):
        """Test wrapping successful operation"""
        mock_handle_error.return_value = True
        operation = Mock(return_value="success")

        result = wrap_operation(operation, "test context")
        assert result == "success"
        operation.assert_called_once()

    @patch('src.error_handler.handle_error')
    def test_wrap_operation_failure_recoverable(self, mock_handle_error):
        """Test wrapping operation with recoverable error"""
        mock_handle_error.return_value = True
        operation = Mock(side_effect=ValueError("Recoverable"))

        result = wrap_operation(operation, "test context")
        assert result is None  # Returns None when handled

    @patch('src.error_handler.handle_error')
    def test_wrap_operation_failure_critical(self, mock_handle_error):
        """Test wrapping operation with critical error"""
        mock_handle_error.return_value = False
        operation = Mock(side_effect=FileNotFoundError("Critical"))

        with pytest.raises(FileNotFoundError):
            wrap_operation(operation, "test context")


class TestSetGuiErrorCallback:
    """Test GUI callback management"""

    def test_set_callback(self):
        """Test setting GUI callback"""
        callback = Mock()
        set_gui_error_callback(callback)
        # Should not raise

    def test_set_callback_none(self):
        """Test clearing GUI callback"""
        set_gui_error_callback(None)
        # Should not raise

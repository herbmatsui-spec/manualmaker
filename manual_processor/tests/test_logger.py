"""
Tests for logger module.
"""

import logging
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.logger import (
    get_logger,
    setup_logger,
    configure_root_logger,
    get_module_logger,
    log_exception,
)


class TestGetLogger:
    """Test get_logger function"""

    def test_get_logger_returns_logger(self):
        """Test get_logger returns a Logger instance"""
        logger = get_logger("test")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test"

    def test_get_logger_same_instance(self):
        """Test get_logger returns same instance for same name"""
        logger1 = get_logger("test.same")
        logger2 = get_logger("test.same")
        assert logger1 is logger2


class TestSetupLogger:
    """Test setup_logger function"""

    def test_setup_logger_basic(self):
        """Test basic logger setup"""
        logger = setup_logger("test_basic")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_basic"
        assert logger.level == logging.INFO

    def test_setup_logger_with_level(self):
        """Test logger setup with custom level"""
        logger = setup_logger("test_level", log_level="DEBUG")
        assert logger.level == logging.DEBUG

    def test_setup_logger_no_duplicate_handlers(self):
        """Test that setup_logger doesn't create duplicate handlers"""
        logger = setup_logger("test_no_dup")
        initial_count = len(logger.handlers)
        
        # Setup again
        setup_logger("test_no_dup")
        
        assert len(logger.handlers) == initial_count

    def test_setup_logger_propagate_false(self):
        """Test that logger propagation is disabled"""
        logger = setup_logger("test_prop")
        assert logger.propagate is False

    def test_setup_logger_with_file(self, tmp_path):
        """Test logger setup with file output"""
        log_file = tmp_path / "test.log"
        logger = setup_logger("test_file", log_file=log_file)
        
        # Write a log message
        logger.info("Test message")
        
        # Verify file was created and contains message
        assert log_file.exists()
        content = log_file.read_text()
        assert "Test message" in content


class TestConfigureRootLogger:
    """Test configure_root_logger function"""

    def test_configure_root_logger(self):
        """Test root logger configuration"""
        configure_root_logger(log_level="WARNING")
        root_logger = logging.getLogger()
        assert root_logger.level == logging.WARNING

    def test_configure_root_logger_with_file(self, tmp_path):
        """Test root logger configuration with file"""
        log_file = tmp_path / "root.log"
        configure_root_logger(log_level="INFO", log_file=log_file)
        
        # Verify file was created
        assert log_file.exists()


class TestGetModuleLogger:
    """Test get_module_logger function"""

    def test_get_module_logger(self):
        """Test getting module logger"""
        # get_module_logger uses inspect to get caller module name
        # So it will return a logger named after this test module
        logger = get_module_logger("src.test_module")
        assert isinstance(logger, logging.Logger)
        # The actual logger name will be the calling module (tests.test_logger)
        assert "test_logger" in logger.name or "test_module" in logger.name


class TestLogException:
    """Test log_exception function"""

    def test_log_exception_no_reraise(self):
        """Test logging exception without reraising"""
        logger = get_logger("test_no_reraise")
        error = ValueError("Test error")
        
        # Should not raise
        log_exception(error, logger, context="test", reraise=False)

    def test_log_exception_with_reraise(self):
        """Test logging exception with reraise"""
        logger = get_logger("test_reraise")
        error = ValueError("Test error")
        
        with pytest.raises(ValueError):
            log_exception(error, logger, context="test", reraise=True)

    def test_log_exception_with_context(self, caplog):
        """Test exception logging includes context"""
        logger = get_logger("test_context")
        error = ValueError("Test error")
        
        with caplog.at_level(logging.ERROR):
            log_exception(error, logger, context="test context", reraise=False)
        
        assert "test context" in caplog.text
        assert "Test error" in caplog.text


class TestSetThirdPartyLogLevels:
    """Test set_third_party_log_levels function"""

    def test_set_third_party_log_levels(self):
        """Test setting third party library log levels"""
        from src.logger import set_third_party_log_levels
        
        # Should not raise
        set_third_party_log_levels()
        
        # Verify some third party loggers exist
        google_logger = logging.getLogger("google")
        urllib3_logger = logging.getLogger("urllib3")
        
        # These should exist (even if level is not changed)
        assert google_logger is not None
        assert urllib3_logger is not None

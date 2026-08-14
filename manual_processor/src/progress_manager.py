"""
Progress Reporting & Cancellation System (Step 12)
Provides CancellationToken and ProgressTracker for long-running workflows.
"""

import logging
import threading
from typing import Callable, Optional, Dict, Any
from dataclasses import dataclass, field
import time

logger = logging.getLogger(__name__)


class OperationCancelledError(Exception):
    """Exception raised when an operation is cancelled via CancellationToken"""
    pass


class CancellationToken:
    """Thread-safe cancellation token"""

    def __init__(self):
        self._is_cancelled = threading.Event()

    def cancel(self) -> None:
        """Trigger cancellation"""
        self._is_cancelled.set()
        logger.info("CancellationToken: Cancellation requested.")

    @property
    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested"""
        return self._is_cancelled.is_set()

    def throw_if_cancelled(self) -> None:
        """Raise OperationCancelledError if token is cancelled"""
        if self.is_cancelled:
            raise OperationCancelledError("Operation was cancelled by user.")

    # 後方互換エイリアス
    throwIfCancelled = throw_if_cancelled


@dataclass
class ProgressStatus:
    """Progress status container"""
    stage: str
    percentage: float  # 0.0 to 100.0
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class ProgressTracker:
    """Tracks operation progress and notifies listeners"""

    def __init__(self, callback: Optional[Callable[[ProgressStatus], None]] = None):
        self.callback = callback
        self.current_status: Optional[ProgressStatus] = None

    def update(self, stage: str, percentage: float, message: str = "", details: Optional[Dict[str, Any]] = None) -> None:
        """Update progress status and invoke callback"""
        status = ProgressStatus(
            stage=stage,
            percentage=max(0.0, min(100.0, percentage)),
            message=message,
            details=details or {}
        )
        self.current_status = status
        logger.debug(f"Progress ({status.percentage:.1f}%): [{stage}] {message}")
        if self.callback:
            try:
                self.callback(status)
            except Exception as e:
                logger.error(f"ProgressTracker callback error: {e}")

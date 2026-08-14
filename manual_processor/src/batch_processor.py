"""
Batch Processing & Directory Monitoring Module (Step 13)
Supports bulk PDF processing, directory watching, and result aggregation.
"""

import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from queue import PriorityQueue
from dataclasses import dataclass, field

from src.progress_manager import CancellationToken, ProgressTracker

logger = logging.getLogger(__name__)


@dataclass(order=True)
class BatchJob:
    """Prioritized batch job item"""
    priority: int
    file_path: Path = field(compare=False)
    added_time: float = field(default_factory=time.time, compare=False)


class BatchProcessor:
    """Batch document processing manager"""

    def __init__(self, processor_instance: Any):
        self.processor = processor_instance
        self.queue: PriorityQueue = PriorityQueue()

    def add_file(self, file_path: Path, priority: int = 10) -> None:
        """Add file to processing queue (lower integer = higher priority)"""
        self.queue.put(BatchJob(priority=priority, file_path=file_path))
        logger.info(f"BatchProcessor: Queued {file_path.name} (Priority {priority})")

    def add_directory(self, dir_path: Path, extensions: Optional[List[str]] = None) -> int:
        """Scan directory and add matching files to queue"""
        if not dir_path.exists() or not dir_path.is_dir():
            raise FileNotFoundError(f"Directory not found: {dir_path}")

        valid_exts = [e.lower() for e in (extensions or ['.pdf'])]
        count = 0
        for item in dir_path.glob("**/*"):
            if item.is_file() and item.suffix.lower() in valid_exts:
                self.add_file(item)
                count += 1
        return count

    def process_all(
        self,
        cancel_token: Optional[CancellationToken] = None,
        progress_tracker: Optional[ProgressTracker] = None
    ) -> Dict[str, Any]:
        """Process all queued jobs and return aggregated summary"""
        results = []
        total_jobs = self.queue.qsize()
        processed_count = 0
        failure_count = 0

        logger.info(f"BatchProcessor: Starting processing of {total_jobs} jobs...")

        while not self.queue.empty():
            if cancel_token and cancel_token.is_cancelled:
                logger.info("BatchProcessor: Batch processing cancelled.")
                break

            job: BatchJob = self.queue.get()
            processed_count += 1

            if progress_tracker:
                pct = (processed_count / total_jobs) * 100.0 if total_jobs > 0 else 100.0
                progress_tracker.update("batch_processing", pct, f"Processing {job.file_path.name} ({processed_count}/{total_jobs})")

            try:
                res = self.processor.process_pdf(job.file_path)
                results.append(res)
                if not res.get("success", True):
                    failure_count += 1
            except Exception as e:
                logger.error(f"BatchProcessor: Error processing {job.file_path.name}: {e}")
                failure_count += 1
                results.append({
                    "success": False,
                    "input_file": str(job.file_path),
                    "error": str(e)
                })

        return {
            "total_jobs": total_jobs,
            "processed": processed_count,
            "failed": failure_count,
            "successful": processed_count - failure_count,
            "results": results
        }

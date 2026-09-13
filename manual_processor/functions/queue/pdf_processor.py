"""
Cloudflare Queue Consumer for async PDF processing
With DLQ handling, retry logic, and observability
"""

import json
import logging
import time
import uuid
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ProcessingStatus(Enum):
    """Processing status enum"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD_LETTER = "dead_letter"


@dataclass
class QueueMessage:
    """Queue message structure"""
    file_id: str
    pdf_key: str
    options: Dict[str, Any]
    timestamp: Optional[float] = None
    retry_count: int = 0
    status: ProcessingStatus = ProcessingStatus.PENDING
    error: Optional[str] = None
    processing_start_time: Optional[float] = None
    processing_end_time: Optional[float] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QueueMessage':
        return cls(
            file_id=data["file_id"],
            pdf_key=data["pdf_key"],
            options=data.get("options", {}),
            timestamp=data.get("timestamp"),
            retry_count=data.get("retry_count", 0),
            status=ProcessingStatus(data.get("status", "pending")),
            error=data.get("error"),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_id": self.file_id,
            "pdf_key": self.pdf_key,
            "options": self.options,
            "timestamp": self.timestamp or time.time(),
            "retry_count": self.retry_count,
            "status": self.status.value,
            "error": self.error,
        }


@dataclass
class ProcessingMetrics:
    """Metrics for queue processing"""
    total_messages: int = 0
    successful: int = 0
    failed: int = 0
    retried: int = 0
    dead_lettered: int = 0
    total_processing_time_ms: float = 0.0
    errors_by_type: Dict[str, int] = field(default_factory=dict)
    
    def record_success(self, processing_time_ms: float):
        self.successful += 1
        self.total_processing_time_ms += processing_time_ms
    
    def record_failure(self, error: Exception):
        self.failed += 1
        error_type = type(error).__name__
        self.errors_by_type[error_type] = self.errors_by_type.get(error_type, 0) + 1
    
    def record_retry(self):
        self.retried += 1
    
    def record_dead_letter(self):
        self.dead_lettered += 1
    
    def to_dict(self) -> Dict[str, Any]:
        avg_time = 0
        if self.successful > 0:
            avg_time = self.total_processing_time_ms / self.successful
        return {
            "total_messages": self.total_messages,
            "successful": self.successful,
            "failed": self.failed,
            "retried": self.retried,
            "dead_lettered": self.dead_lettered,
            "success_rate": self.successful / max(self.total_messages, 1),
            "avg_processing_time_ms": round(avg_time, 2),
            "errors_by_type": self.errors_by_type,
        }


# Global metrics instance
_metrics = ProcessingMetrics()


def get_metrics() -> ProcessingMetrics:
    """Get global metrics instance"""
    return _metrics


def reset_metrics():
    """Reset metrics (for testing)"""
    global _metrics
    _metrics = ProcessingMetrics()


MAX_RETRIES = 3
RETRY_DELAYS = [1, 5, 30]  # seconds


async def send_to_dlq(message: QueueMessage, env: Any, error: str):
    """Send failed message to Dead Letter Queue"""
    try:
        if hasattr(env, 'PDF_DLQ'):
            dlq_message = message.to_dict()
            dlq_message["dlq_timestamp"] = time.time()
            dlq_message["final_error"] = error
            await env.PDF_DLQ.send(dlq_message)
            logger.info(f"Sent message {message.file_id} to DLQ")
            _metrics.record_dead_letter()
        else:
            logger.warning("DLQ not configured, cannot send dead letter")
    except Exception as e:
        logger.error(f"Failed to send to DLQ: {e}")


async def process_pdf_queue_message(
    message: QueueMessage,
    env: Any,
    config: Any
) -> Dict[str, Any]:
    """
    Process a PDF from queue message.
    This runs in the Queue consumer context.
    """
    from src.r2_storage import get_file_manager
    from src.processor.processor import DocumentProcessor
    from config.config import Config
    from functions._middleware import log_structured
    
    file_manager = get_file_manager(env.FILES)
    processing_start = time.time()
    
    # Update status to processing
    message.status = ProcessingStatus.PROCESSING
    message.processing_start_time = processing_start
    
    # Update progress via Durable Object
    if hasattr(env, 'PROGRESS_DO'):
        try:
            stub = env.PROGRESS_DO.id_from_name(message.file_id)
            await stub.fetch(f"https://do/progress/{message.file_id}", method="POST", body=json.dumps({
                "status": "processing",
                "progress": 10,
                "stage": "PDFをダウンロード中..."
            }))
        except Exception as e:
            logger.warning(f"Failed to update progress DO: {e}")
    
    try:
        # Download PDF from R2
        log_structured("info", "Downloading PDF from R2", file_id=message.file_id, pdf_key=message.pdf_key)
        pdf_data = file_manager.r2.download_file(message.pdf_key)
        
        # Update progress
        if hasattr(env, 'PROGRESS_DO'):
            try:
                stub = env.PROGRESS_DO.id_from_name(message.file_id)
                await stub.fetch(f"https://do/progress/{message.file_id}", method="POST", body=json.dumps({
                    "status": "processing",
                    "progress": 20,
                    "stage": "OCR処理中..."
                }))
            except Exception:
                pass
        
        # Save to temp file for processing
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp.write(pdf_data)
            tmp_path = Path(tmp.name)
        
        try:
            # Initialize processor
            processor = DocumentProcessor(config)
            
            # Update progress
            if hasattr(env, 'PROGRESS_DO'):
                try:
                    stub = env.PROGRESS_DO.id_from_name(message.file_id)
                    await stub.fetch(f"https://do/progress/{message.file_id}", method="POST", body=json.dumps({
                        "status": "processing",
                        "progress": 40,
                        "stage": "AI要約生成中..."
                    }))
                except Exception:
                    pass
            
            # Process PDF
            result = processor.process_pdf(
                tmp_path,
                compact_layout=message.options.get("compact_layout", False),
                use_emojis=message.options.get("use_emojis", False),
                file_id=message.file_id,
                base_url=message.options.get("base_url", "https://manual-processor.pages.dev")
            )
            
            # Update progress
            if hasattr(env, 'PROGRESS_DO'):
                try:
                    stub = env.PROGRESS_DO.id_from_name(message.file_id)
                    await stub.fetch(f"https://do/progress/{message.file_id}", method="POST", body=json.dumps({
                        "status": "processing",
                        "progress": 80,
                        "stage": "出力ファイル生成中..."
                    }))
                except Exception:
                    pass
            
            # Save result to R2
            file_manager.save_json_result(message.file_id, result)
            
            # If there are output files, upload them
            outputs = result.get("output_files", {})
            for output_type, file_path_str in outputs.items():
                if file_path_str:
                    file_path = Path(file_path_str)
                    if file_path.exists():
                        with open(file_path, 'rb') as f:
                            file_data = f.read()
                        file_manager.save_result(
                            message.file_id, 
                            output_type, 
                            file_data, 
                            file_path.name
                        )
            
            processing_end = time.time()
            processing_time_ms = (processing_end - processing_start) * 1000
            
            # Update progress - completed
            if hasattr(env, 'PROGRESS_DO'):
                try:
                    stub = env.PROGRESS_DO.id_from_name(message.file_id)
                    await stub.fetch(f"https://do/progress/{message.file_id}", method="POST", body=json.dumps({
                        "status": "completed",
                        "progress": 100,
                        "stage": "完了",
                        "result": result,
                        "processing_time_ms": processing_time_ms
                    }))
                except Exception as e:
                    logger.warning(f"Failed to update progress DO: {e}")
            
            # Record metrics
            _metrics.record_success(processing_time_ms)
            
            log_structured("info", "PDF processing completed", 
                file_id=message.file_id, 
                processing_time_ms=processing_time_ms,
                success=True
            )
            
            return {"success": True, "file_id": message.file_id, "processing_time_ms": processing_time_ms}
            
        finally:
            # Cleanup temp file
            try:
                tmp_path.unlink()
            except Exception:
                pass
    
    except Exception as e:
        processing_end = time.time()
        processing_time_ms = (processing_end - processing_start) * 1000
        
        logger.error(f"Queue processing error for {message.file_id}: {e}", exc_info=True)
        
        # Record metrics
        _metrics.record_failure(e)
        
        # Save error result
        error_result = {
            "success": False,
            "file_id": message.file_id,
            "error": str(e),
            "error_type": type(e).__name__,
            "processing_time_ms": processing_time_ms,
            "retry_count": message.retry_count
        }
        file_manager.save_json_result(message.file_id, error_result)
        
        # Update progress with error
        if hasattr(env, 'PROGRESS_DO'):
            try:
                stub = env.PROGRESS_DO.id_from_name(message.file_id)
                await stub.fetch(f"https://do/progress/{message.file_id}", method="POST", body=json.dumps({
                    "status": "error",
                    "progress": 0,
                    "stage": "エラー",
                    "error": str(e),
                    "processing_time_ms": processing_time_ms
                }))
            except Exception:
                pass
        
        log_structured("error", "PDF processing failed", 
            file_id=message.file_id, 
            error=str(e),
            error_type=type(e).__name__,
            processing_time_ms=processing_time_ms,
            retry_count=message.retry_count
        )
        
        return {"success": False, "file_id": message.file_id, "error": str(e), "processing_time_ms": processing_time_ms}


# Queue consumer entry point for Pages Functions
async def queue_consumer(batch: Any, env: Any, ctx: Any) -> None:
    """
    Cloudflare Queue consumer handler with retry logic and DLQ.
    Receives batch of messages and processes them.
    """
    from config.config import Config
    
    config = Config.get_instance()
    
    for message in batch.messages:
        _metrics.total_messages += 1
        
        try:
            queue_msg = QueueMessage.from_dict(message.body)
            
            # Check retry count
            if queue_msg.retry_count >= MAX_RETRIES:
                logger.warning(f"Message {queue_msg.file_id} exceeded max retries, sending to DLQ")
                await send_to_dlq(queue_msg, env, f"Max retries ({MAX_RETRIES}) exceeded")
                message.ack()  # Ack to remove from main queue
                continue
            
            # Process message
            result = await process_pdf_queue_message(queue_msg, env, config)
            
            if result.get("success"):
                message.ack()
            else:
                # Handle retry logic
                queue_msg.retry_count += 1
                queue_msg.status = ProcessingStatus.RETRYING
                queue_msg.error = result.get("error")
                
                # Calculate retry delay (exponential backoff)
                delay_index = min(queue_msg.retry_count - 1, len(RETRY_DELAYS) - 1)
                retry_delay = RETRY_DELAYS[delay_index]
                
                # Re-queue with delay
                retry_message = queue_msg.to_dict()
                retry_message["retry_delay"] = retry_delay
                
                if hasattr(env, 'PDF_QUEUE'):
                    # Schedule retry by sending with delay
                    # Note: Cloudflare Queues doesn't support native delay, so we re-send
                    await env.PDF_QUEUE.send(retry_message)
                    logger.info(f"Re-queued message {queue_msg.file_id} for retry #{queue_msg.retry_count} after {retry_delay}s")
                    _metrics.record_retry()
                else:
                    logger.error("PDF_QUEUE not configured, cannot retry")
                    await send_to_dlq(queue_msg, env, "Queue not configured for retry")
                
                message.ack()  # Ack original message
                
        except Exception as e:
            logger.error(f"Failed to process queue message: {e}", exc_info=True)
            # Don't ack - let queue retry automatically
            message.retry()


# Health check for queue consumer
async def health_check(env: Any) -> Dict[str, Any]:
    """Health check endpoint for queue consumer"""
    metrics = get_metrics().to_dict()
    return {
        "status": "healthy",
        "metrics": metrics,
        "queue_configured": hasattr(env, 'PDF_QUEUE'),
        "dlq_configured": hasattr(env, 'PDF_DLQ'),
        "progress_do_configured": hasattr(env, 'PROGRESS_DO'),
        "r2_configured": hasattr(env, 'FILES'),
    }


# For local testing
if __name__ == "__main__":
    import asyncio
    
    async def test():
        # Mock env for testing
        class MockEnv:
            FILES = None
            PROGRESS_DO = None
            PDF_QUEUE = None
            PDF_DLQ = None
        
        msg = QueueMessage(
            file_id="test-123",
            pdf_key="uploads/test-123/test.pdf",
            options={"compact_layout": False, "use_emojis": False}
        )
        
        result = await process_pdf_queue_message(msg, MockEnv(), Config.get_instance())
        print(result)
        
        print("Metrics:", get_metrics().to_dict())
    
    asyncio.run(test())
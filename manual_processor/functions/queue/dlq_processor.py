"""
Dead Letter Queue Processor for failed PDF processing messages
Handles alerting, logging, and potential manual retry
"""

import json
import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


async def dlq_processor(batch: Any, env: Any, ctx: Any) -> None:
    """
    Cloudflare DLQ consumer handler.
    Processes messages that have failed all retries.
    """
    for message in batch.messages:
        try:
            dlq_data = message.body
            file_id = dlq_data.get("file_id", "unknown")
            final_error = dlq_data.get("final_error", "Unknown error")
            retry_count = dlq_data.get("retry_count", 0)
            dlq_timestamp = dlq_data.get("dlq_timestamp")
            
            logger.error(f"DLQ Message received: file_id={file_id}, error={final_error}, retries={retry_count}")
            
            # Log structured data for monitoring
            log_dlq_entry = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "file_id": file_id,
                "error": final_error,
                "retry_count": retry_count,
                "original_timestamp": dlq_data.get("timestamp"),
                "dlq_timestamp": dlq_timestamp,
                "pdf_key": dlq_data.get("pdf_key"),
                "options": dlq_data.get("options"),
            }
            
            # In production, you could:
            # 1. Send alert to PagerDuty, Slack, email
            # 2. Store in D1 database for manual review
            # 3. Trigger manual retry workflow
            # 4. Send to external error tracking (Sentry, etc.)
            
            # For now, just log
            logger.error(f"DLQ Entry: {json.dumps(log_dlq_entry, ensure_ascii=False)}")
            
            # Optionally store in R2 for later analysis
            if hasattr(env, 'FILES'):
                try:
                    from src.r2_storage import get_file_manager
                    file_manager = get_file_manager(env.FILES)
                    dlq_key = f"dlq/{file_id}_{int(dlq_timestamp or 0)}.json"
                    file_manager.r2.upload_file(
                        json.dumps(log_dlq_entry, ensure_ascii=False).encode('utf-8'),
                        dlq_key,
                        content_type="application/json"
                    )
                except Exception as e:
                    logger.warning(f"Failed to store DLQ entry in R2: {e}")
            
            # Ack the message (remove from DLQ)
            message.ack()
            
        except Exception as e:
            logger.error(f"Failed to process DLQ message: {e}", exc_info=True)
            # Don't ack - let it stay in DLQ for manual inspection


# Health check for DLQ processor
async def dlq_health_check(env: Any) -> Dict[str, Any]:
    """Health check endpoint for DLQ processor"""
    return {
        "status": "healthy",
        "dlq_configured": hasattr(env, 'FILES'),
        "r2_configured": hasattr(env, 'FILES'),
    }


# For local testing
if __name__ == "__main__":
    import asyncio
    
    async def test():
        class MockEnv:
            FILES = None
        
        class MockMessage:
            def __init__(self, body):
                self.body = body
                self.acked = False
            
            def ack(self):
                self.acked = True
        
        class MockBatch:
            def __init__(self, messages):
                self.messages = messages
        
        # Test message
        test_msg = MockMessage({
            "file_id": "test-dlq-123",
            "pdf_key": "uploads/test-dlq-123/test.pdf",
            "options": {"compact_layout": False},
            "retry_count": 3,
            "final_error": "PDF processing timeout",
            "dlq_timestamp": 1234567890,
            "timestamp": 1234567800,
        })
        
        batch = MockBatch([test_msg])
        await dlq_processor(batch, MockEnv(), None)
        print("DLQ processor test completed")
    
    asyncio.run(test())
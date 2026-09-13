"""
Pages Functions Queue Consumer Entry Point
"""

from functions.queue.pdf_processor import queue_consumer, health_check, get_metrics, reset_metrics
from functions.queue.dlq_processor import dlq_processor, dlq_health_check


export = {
    "queue": queue_consumer,
    "health_check": health_check,
    "get_metrics": get_metrics,
    "reset_metrics": reset_metrics,
    "dlq": dlq_processor,
    "dlq_health_check": dlq_health_check,
}
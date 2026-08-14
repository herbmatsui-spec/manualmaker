"""
Processor Factory Module (Step 10)
Supports configuration-based processor selection and fallback logic.
"""

import logging
from typing import Optional, Dict, Any
from config.config import AppConfig
from src.gemini_processor import GeminiProcessor, GeminiResult, Section
from src.exceptions import GeminiAPIError, ProcessingError

logger = logging.getLogger(__name__)


class LocalProcessor:
    """Local fallback processor for offline / mock summarization"""

    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config

    def process_document(self, text: str, target_audience: str = "beginner") -> GeminiResult:
        """Process document using local heuristics"""
        if not text or not text.strip():
            return GeminiResult(summary="", key_points=[], sections=[], difficulty_level=target_audience)

        lines = [line.strip() for line in text.split('\n') if line.strip()]
        summary = lines[0] if lines else "ローカル処理結果"
        key_points = lines[1:6] if len(lines) > 1 else [summary]

        sections = [
            Section(title="概要 (ローカル)", content=summary),
            Section(title="重要ポイント (ローカル)", content="\n".join(key_points))
        ]

        return GeminiResult(
            summary=summary,
            key_points=key_points,
            sections=sections,
            difficulty_level=target_audience,
            title="ローカル要約マニュアル"
        )


class HybridProcessor:
    """Hybrid processor combining Gemini API with Local fallback"""

    def __init__(self, gemini_processor: GeminiProcessor, local_processor: LocalProcessor):
        self.gemini = gemini_processor
        self.local = local_processor

    def process_document(self, text: str, target_audience: str = "beginner") -> GeminiResult:
        try:
            return self.gemini.process_document(text, target_audience)
        except Exception as e:
            logger.warning(f"HybridProcessor: Primary Gemini processor failed ({e}), falling back to LocalProcessor.")
            return self.local.process_document(text, target_audience)


class ProcessorFactory:
    """Factory class to create document processors based on configuration"""

    @staticmethod
    def create_processor(config: Optional[AppConfig] = None, processor_type: Optional[str] = None):
        cfg = config or AppConfig.get_instance() if hasattr(AppConfig, 'get_instance') else config
        ptype = (processor_type or getattr(cfg, 'processor_type', 'gemini')).lower()

        logger.info(f"ProcessorFactory: Creating processor of type '{ptype}'")

        local_proc = LocalProcessor(cfg)

        if ptype == "local":
            return local_proc

        # Attempt to instantiate GeminiProcessor
        try:
            api_key = getattr(cfg, 'gemini_api_key', None) or getattr(cfg, 'google_api_key', None)
            gemini_proc = GeminiProcessor(
                api_key=api_key,
                model_name=getattr(cfg, 'gemini_model_name', 'gemini-1.5-flash'),
                temperature=getattr(cfg, 'gemini_temperature', 0.3),
                max_output_tokens=getattr(cfg, 'gemini_max_output_tokens', 2048)
            )

            if ptype == "hybrid" or getattr(cfg, 'fallback_enabled', True):
                return HybridProcessor(gemini_proc, local_proc)
            return gemini_proc

        except Exception as e:
            if getattr(cfg, 'fallback_enabled', True):
                logger.warning(f"ProcessorFactory: Gemini initialization failed ({e}). Falling back to LocalProcessor.")
                return local_proc
            raise ProcessingError(f"Failed to initialize requested processor '{ptype}': {e}")

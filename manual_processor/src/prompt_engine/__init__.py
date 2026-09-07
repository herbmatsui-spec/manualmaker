"""
Prompt Engine Module
Handwritten PDF transcription prompt system
"""

from src.prompt_engine.prompt_builder import HandwrittenPromptBuilder, PromptConfig
from src.prompt_engine.prompt_templates import (
    LITERAL_TRANSCRIPTION_RULE,
    UNREADABLE_CHAR_RULE,
    RUBY_IGNORANCE_RULE,
    NOISE_EXCLUSION_RULE,
    LAYOUT_RULE_HORIZONTAL,
    LAYOUT_RULE_VERTICAL,
    DOMAIN_GLOSSARY_RULE,
    DIAGRAM_STRUCTURE_RULE,
    LOW_QUALITY_RULE,
)
from src.prompt_engine.i18n_templates import get_translation, LANGUAGE_CODES
from src.exceptions import PromptEngineError

__all__ = [
    "HandwrittenPromptBuilder",
    "PromptConfig",
    "LITERAL_TRANSCRIPTION_RULE",
    "UNREADABLE_CHAR_RULE",
    "RUBY_IGNORANCE_RULE",
    "NOISE_EXCLUSION_RULE",
    "LAYOUT_RULE_HORIZONTAL",
    "LAYOUT_RULE_VERTICAL",
    "DOMAIN_GLOSSARY_RULE",
    "DIAGRAM_STRUCTURE_RULE",
    "LOW_QUALITY_RULE",
    "get_translation",
    "LANGUAGE_CODES",
    "PromptEngineError",
]

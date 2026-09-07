"""
Prompt Builder Module
Builds prompts for handwritten PDF transcription addressing the 9 common problems
"""

import logging
import json
from dataclasses import dataclass, field
from typing import List, Optional

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
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_HEADER,
    DEFAULT_OUTPUT_FORMAT,
)
from src.prompt_engine.i18n_templates import get_translation
from src.exceptions import PromptEngineError
from src.cache_manager import CacheManager

logger = logging.getLogger(__name__)


@dataclass
class PromptConfig:
    """Configuration for prompt building"""
    layout: str = "horizontal"
    domain_terms: List[str] = field(default_factory=list)
    has_diagrams: bool = False
    low_quality_mode: bool = False
    strict_mode: bool = True
    language: str = "ja"
    custom_rules: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.layout not in ("horizontal", "vertical"):
            self.layout = "horizontal"
        if self.language not in ("ja", "en", "zh"):
            self.language = "ja"


class HandwrittenPromptBuilder:
    """Builder for handwritten PDF transcription prompts"""

    def __init__(self, config: Optional[PromptConfig] = None,
                 cache_manager: Optional[CacheManager] = None):
        self.config = config or PromptConfig()
        self.cache_manager = cache_manager
        self._rules: List[str] = []
        self._header_added = False
        self._system_prompt_added = False

    def _translated_rule(self, key: str, fallback: str) -> str:
        """Return a localized rule while preserving the Japanese default text."""
        if self.config.language == "ja":
            return fallback
        return get_translation(self.config.language, key)

    @classmethod
    def from_config(cls, app_config, cache_manager: Optional[CacheManager] = None) -> "HandwrittenPromptBuilder":
        """Create a builder from an AppConfig-like object."""
        config = PromptConfig(
            layout=getattr(app_config, "prompt_layout", "horizontal"),
            domain_terms=list(getattr(app_config, "prompt_domain_terms", [])),
            has_diagrams=bool(getattr(app_config, "prompt_has_diagrams", False)),
            low_quality_mode=bool(getattr(app_config, "prompt_low_quality_mode", False)),
            strict_mode=bool(getattr(app_config, "prompt_strict_mode", True)),
            custom_rules=list(getattr(app_config, "prompt_custom_rules", [])),
            language=getattr(app_config, "default_language", "ja"),
        )
        return cls(config, cache_manager=cache_manager)

    def _prompt_cache_key(self, layout, domain_terms, has_diagrams, low_quality) -> str:
        """Create a stable cache key from every prompt-affecting option."""
        payload = {
            "layout": layout,
            "domain_terms": list(domain_terms),
            "has_diagrams": has_diagrams,
            "low_quality": low_quality,
            "strict_mode": self.config.strict_mode,
            "language": self.config.language,
            "custom_rules": list(self.config.custom_rules),
        }
        return "prompt-builder:" + json.dumps(payload, ensure_ascii=False, sort_keys=True)

    def reset(self) -> "HandwrittenPromptBuilder":
        """Reset the builder state"""
        self._rules.clear()
        self._header_added = False
        self._system_prompt_added = False
        return self

    def add_system_prompt(self) -> "HandwrittenPromptBuilder":
        """Add the system prompt prefix"""
        if not self._system_prompt_added:
            self._rules.insert(0, get_translation(self.config.language, "system_prompt"))
            self._system_prompt_added = True
        return self

    def add_header(self) -> "HandwrittenPromptBuilder":
        """Add the instruction header"""
        if not self._header_added:
            self._rules.append(get_translation(self.config.language, "header"))
            self._header_added = True
        return self

    def no_summarize(self) -> "HandwrittenPromptBuilder":
        """Add rule to prevent summarization (addresses problem 9)"""
        self._rules.append(self._translated_rule("transcription_rule", LITERAL_TRANSCRIPTION_RULE))
        return self

    def mark_unreadable(self, marker: str = "●") -> "HandwrittenPromptBuilder":
        """Add rule to mark unreadable characters (addresses problems 1, 2, 6)"""
        rule = self._translated_rule("unreadable_rule", UNREADABLE_CHAR_RULE).replace("●", marker)
        self._rules.append(rule)
        return self

    def add_confusing_chars_warning(self) -> "HandwrittenPromptBuilder":
        """Add explicit warning about similar character confusion (addresses problem 1)"""
        confusing_chars_rule = """8. 類似文字の注意：以下の類似文字の組合せに注意してください。必ず文脈から判断せず、画像の状態を正確に読み取ってください。
   - 「シ」と「ツ」（カタカナ）
   - 「ソ」と「ン」（カタカナ）
   - 「0（ゼロ）」と「O（オー）」と「D（ディー）」と「Q（キュー）」
   - 「1（数字のいち）」と「l（小文字のエル）」と「I（大文字のアイ）」
   - 「一（漢字）」と「ー（長音記号）」と「━（横線）」
   - 「ニ」と「二」、「三与之」
   - 「め」と「ぬ」、「る」と「ろ」
   - 「仝」と「人」、「大」と「太」"""
        if self.config.language == "ja":
            self._rules.append(confusing_chars_rule)
        else:
            self._rules.append(get_translation(self.config.language, "confusing_chars"))
        return self

    def ignore_ruby(self) -> "HandwrittenPromptBuilder":
        """Add rule to ignore ruby text (addresses problem 4)"""
        self._rules.append(self._translated_rule("ruby_rule", RUBY_IGNORANCE_RULE))
        return self

    def exclude_noise(self) -> "HandwrittenPromptBuilder":
        """Add rule to exclude noise like grid lines (addresses problem 5)"""
        self._rules.append(self._translated_rule("noise_rule", NOISE_EXCLUSION_RULE))
        return self

    def set_layout(self, layout: str = "horizontal") -> "HandwrittenPromptBuilder":
        """Add layout rule for reading direction (addresses problem 3)"""
        self.config.layout = layout
        if layout == "vertical":
            rule = self._translated_rule("layout_vertical", LAYOUT_RULE_VERTICAL)
        else:
            rule = self._translated_rule("layout_horizontal", LAYOUT_RULE_HORIZONTAL)
        self._rules.append(rule)
        return self

    def add_domain_terms(self, terms: List[str]) -> "HandwrittenPromptBuilder":
        """Add domain-specific terms to help recognition (addresses problem 6)"""
        self.config.domain_terms.extend(terms)
        if terms:
            terms_list = "\n".join(f"・{term}" for term in terms)
            rule = self._translated_rule("domain_glossary", DOMAIN_GLOSSARY_RULE).format(
                domain_terms=terms_list,
                terms=terms_list,
            )
            self._rules.append(rule)
        return self

    def structure_diagrams(self) -> "HandwrittenPromptBuilder":
        """Add rule to structure diagrams (addresses problem 7)"""
        self.config.has_diagrams = True
        self._rules.append(self._translated_rule("diagram_rule", DIAGRAM_STRUCTURE_RULE))
        return self

    def handle_low_quality(self) -> "HandwrittenPromptBuilder":
        """Add rule for low quality image handling (addresses problem 8)"""
        self.config.low_quality_mode = True
        self._rules.append(self._translated_rule("low_quality_rule", LOW_QUALITY_RULE))
        return self

    def add_output_format(self) -> "HandwrittenPromptBuilder":
        """Add output format specification"""
        self._rules.append(DEFAULT_OUTPUT_FORMAT)
        return self

    def add_custom_rules(self, rules: Optional[List[str]] = None) -> "HandwrittenPromptBuilder":
        """Add user-defined prompt fragments after the built-in rules."""
        selected_rules = self.config.custom_rules if rules is None else rules
        for rule in selected_rules:
            if not isinstance(rule, str):
                raise PromptEngineError(
                    "カスタムプロンプトルールは文字列で指定してください",
                    error_code="INVALID_CUSTOM_PROMPT_RULE",
                    user_message="追加プロンプトルールの形式が不正です。",
                )
            normalized_rule = rule.strip()
            if normalized_rule and normalized_rule not in self._rules:
                self._rules.append(normalized_rule)
        return self

    def build_handwritten_transcription_prompt(
        self,
        layout: Optional[str] = None,
        domain_terms: Optional[List[str]] = None,
        has_diagrams: Optional[bool] = None,
        low_quality: Optional[bool] = None,
    ) -> str:
        """Build the complete prompt for a handwritten document.

        The method resets the builder so repeated calls do not duplicate rules.
        Optional values override the current configuration for this build.
        """
        effective_layout = layout or self.config.layout
        effective_terms = list(self.config.domain_terms if domain_terms is None else domain_terms)
        effective_diagrams = self.config.has_diagrams if has_diagrams is None else has_diagrams
        effective_low_quality = (
            self.config.low_quality_mode if low_quality is None else low_quality
        )
        cache_key = None
        if self.cache_manager is not None:
            cache_key = self._prompt_cache_key(
                effective_layout,
                effective_terms,
                effective_diagrams,
                effective_low_quality,
            )
            cached = self.cache_manager.get(cache_key)
            if cached and isinstance(cached.get("prompt"), str):
                return cached["prompt"]

        self.reset()
        self.add_system_prompt().add_header()
        self.no_summarize().mark_unreadable().add_confusing_chars_warning()
        self.ignore_ruby().exclude_noise()
        self.set_layout(effective_layout)

        self.add_domain_terms(effective_terms)

        if effective_diagrams:
            self.structure_diagrams()

        if effective_low_quality:
            self.handle_low_quality()

        self.add_custom_rules().add_output_format()
        if self.cache_manager is not None and cache_key is not None:
            prompt = self.build()
            self.cache_manager.set(cache_key, {"prompt": prompt})
            return prompt
        return self.build()

    def build(self) -> str:
        """Build and return the final prompt string"""
        if not self._rules:
            logger.warning("PromptBuilder: No rules added, returning empty prompt")
            return ""

        prompt_parts = []
        if self._system_prompt_added:
            prompt_parts.append(DEFAULT_SYSTEM_PROMPT)
            prompt_parts.append("")

        if self._header_added:
            prompt_parts.append(DEFAULT_HEADER)
            prompt_parts.append("")

        prompt_parts.append(get_translation(self.config.language, "rule_header"))
        localized_system_prompt = get_translation(self.config.language, "system_prompt")
        localized_header = get_translation(self.config.language, "header")
        for rule in self._rules:
            if rule not in (
                DEFAULT_SYSTEM_PROMPT,
                DEFAULT_HEADER,
                DEFAULT_OUTPUT_FORMAT,
                localized_system_prompt,
                localized_header,
            ):
                prompt_parts.append(rule)

        prompt_parts.append("")
        prompt_parts.append(get_translation(self.config.language, "output_format"))

        return "\n".join(prompt_parts)

    def build_for_gemini(self) -> List[str]:
        """Build prompt as a list of parts for Gemini API"""
        return self.build().split("\n\n")

    def build_processing_context(self) -> str:
        """Build non-contradictory context for downstream text processing.

        The full transcription prompt contains a no-summarization instruction,
        so it must not be embedded in a summarization request. This method
        exposes only the document characteristics that are useful after OCR.
        """
        lines = ["これは手書き文書から抽出されたOCRテキストです。"]
        if self.config.layout == "vertical":
            lines.append("原文の読み取り方向は縦書きです。")
        else:
            lines.append("原文の読み取り方向は横書きです。")
        if self.config.domain_terms:
            lines.append("専門用語・固有名詞は次の表記を優先してください: " + "、".join(self.config.domain_terms))
        if self.config.has_diagrams:
            lines.append("図解や矢印の関係性が含まれる可能性があります。")
        if self.config.low_quality_mode:
            lines.append("低品質画像由来の判読不能マーカーは推測で置き換えないでください。")
        return "\n".join(lines)

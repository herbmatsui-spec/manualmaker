"""
Multi-language (i18n) & Translation Support Module (Step 16)
Handles locale translations, language detection, and terminology glossary management.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "ja": {
        "app_title": "手書きマニュアル自動整理システム",
        "summary_title": "マニュアル概要",
        "key_points_title": "重要ポイント",
        "sections_title": "詳細セクション",
        "glossary_title": "用語集",
        "processing": "処理中...",
        "completed": "処理完了",
        "failed": "処理失敗"
    },
    "en": {
        "app_title": "Handwritten Manual Automated Processing System",
        "summary_title": "Manual Summary",
        "key_points_title": "Key Points",
        "sections_title": "Detailed Sections",
        "glossary_title": "Glossary",
        "processing": "Processing...",
        "completed": "Completed",
        "failed": "Failed"
    }
}


class I18nManager:
    """Internationalization and localization manager"""

    def __init__(self, default_lang: str = "ja"):
        self.current_lang = default_lang.lower()

    def get_text(self, key: str, lang: Optional[str] = None) -> str:
        """Get translated text for given key and language"""
        target_lang = (lang or self.current_lang).lower()
        lang_dict = TRANSLATIONS.get(target_lang, TRANSLATIONS.get("ja", {}))
        return lang_dict.get(key, key)

    def detect_language(self, text: str) -> str:
        """Detect language (Japanese vs English simple heuristic)"""
        if not text:
            return "ja"
        # Japanese Unicode character ranges check (Hiragana, Katakana, Kanji)
        jp_chars = sum(1 for c in text if '\u3040' <= c <= '\u9fff')
        if jp_chars > len(text) * 0.1:
            return "ja"
        return "en"

"""
Multi-language (i18n) & Translation Support Module (Step 16)
Handles locale translations, language detection, and terminology glossary management.
"""

import logging
from typing import Dict, Any, Optional, List

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
        "failed": "処理失敗",
        "error_title": "エラー",
        "warning_title": "警告",
        "confirm_title": "確認",
        "button_ok": "OK",
        "button_cancel": "キャンセル",
        "button_close": "閉じる"
    },
    "en": {
        "app_title": "Handwritten Manual Automated Processing System",
        "summary_title": "Manual Summary",
        "key_points_title": "Key Points",
        "sections_title": "Detailed Sections",
        "glossary_title": "Glossary",
        "processing": "Processing...",
        "completed": "Completed",
        "failed": "Failed",
        "error_title": "Error",
        "warning_title": "Warning",
        "confirm_title": "Confirm",
        "button_ok": "OK",
        "button_cancel": "Cancel",
        "button_close": "Close"
    },
    "zh": {
        "app_title": "手写手册自动整理系统",
        "summary_title": "手册概要",
        "key_points_title": "重要ポイント",
        "sections_title": "详细章节",
        "glossary_title": "术语表",
        "processing": "处理中...",
        "completed": "处理完成",
        "failed": "处理失败",
        "error_title": "错误",
        "warning_title": "警告",
        "confirm_title": "确认",
        "button_ok": "确定",
        "button_cancel": "取消",
        "button_close": "关闭"
    },
    "ko": {
        "app_title": "손글씨 매뉴얼 자동 정리 시스템",
        "summary_title": "매뉴얼 개요",
        "key_points_title": "중요 포인트",
        "sections_title": "상세 섹션",
        "glossary_title": "용어집",
        "processing": "처리 중...",
        "completed": "처리 완료",
        "failed": "처리 실패",
        "error_title": "오류",
        "warning_title": "경고",
        "confirm_title": "확인",
        "button_ok": "확인",
        "button_cancel": "취소",
        "button_close": "닫기"
    },
    "es": {
        "app_title": "Sistema de Procesamiento Automatizado de Manuales Manuscritos",
        "summary_title": "Resumen del Manual",
        "key_points_title": "Puntos Clave",
        "sections_title": "Secciones Detalladas",
        "glossary_title": "Glosario",
        "processing": "Procesando...",
        "completed": "Completado",
        "failed": "Fallido",
        "error_title": "Error",
        "warning_title": "Advertencia",
        "confirm_title": "Confirmar",
        "button_ok": "Aceptar",
        "button_cancel": "Cancelar",
        "button_close": "Cerrar"
    }
}


class I18nManager:
    """Internationalization and localization manager"""

    LANGUAGE_RANGES: Dict[str, tuple] = {
        "ja": ('\u3040', '\u9fff'),      # Hiragana, Katakana, CJK
        "zh": ('\u4e00', '\u9fff'),      # Chinese
        "ko": ('\uac00', '\ud7af'),      # Korean Hangul
        "es": ('\u00c0', '\u00ff'),      # Spanish/Portuguese accents
    }

    # Expose module-level TRANSLATIONS for backward compatibility
    TRANSLATIONS = TRANSLATIONS

    def __init__(self, default_lang: str = "ja"):
        self.current_lang = default_lang.lower()
        if self.current_lang not in TRANSLATIONS:
            self.current_lang = "ja"

    def set_language(self, lang: str) -> None:
        """Set the current language"""
        self.current_lang = lang.lower()
        if self.current_lang not in TRANSLATIONS:
            self.current_lang = "ja"

    def get_text(self, key: str, lang: Optional[str] = None) -> str:
        """Get translated text for given key and language"""
        target_lang = (lang or self.current_lang).lower()
        lang_dict = TRANSLATIONS.get(target_lang, TRANSLATIONS.get("ja", {}))
        return lang_dict.get(key, key)

    def get_available_languages(self) -> List[str]:
        """Return list of available language codes"""
        return list(TRANSLATIONS.keys())

    def detect_language(self, text: str) -> str:
        """Detect language based on Unicode character ranges"""
        if not text:
            return "ja"

        char_count = len(text)
        if char_count == 0:
            return "ja"

        hiragana_count = sum(1 for c in text if '\u3040' <= c <= '\u309f')
        katakana_count = sum(1 for c in text if '\u30a0' <= c <= '\u30ff')
        kanji_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        korean_count = sum(1 for c in text if '\uac00' <= c <= '\ud7af')
        cjk_ext_count = sum(1 for c in text if '\uf900' <= c <= '\ufaff')

        japanese_score = (hiragana_count + katakana_count * 0.5) / char_count
        chinese_score = kanji_count / char_count
        korean_score = korean_count / char_count

        threshold = 0.05

        if hiragana_count > 0 or katakana_count > 0:
            return "ja"
        elif chinese_score >= threshold and korean_score < threshold:
            return "zh"
        elif korean_score >= threshold:
            return "ko"
        elif char_count <= 50:
            return "en"

        return "en"

"""Tests for src/utils/result_formatter.py"""

import sys
from pathlib import Path

src_path = Path(__file__).resolve().parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from src.utils.result_formatter import format_to_markdown
from src.gemini_processor import GeminiResult
from src.models import Section


class TestFormatToMarkdown:
    def test_string_passthrough(self):
        assert format_to_markdown("hello") == "hello"

    def test_unknown_type_uses_str(self):
        class Weird:
            def __str__(self):
                return "weird-repr"

        assert format_to_markdown(Weird()) == "weird-repr"

    def test_dict_minimal(self):
        md = format_to_markdown({"title": "Doc", "summary": "S"})
        assert "# Doc" in md
        assert "## 概要" in md
        assert "S" in md

    def test_dict_with_key_points(self):
        md = format_to_markdown({
            "title": "T",
            "key_points": ["a", "b"],
        })
        assert "- a" in md
        assert "- b" in md

    def test_dict_with_sections_as_dicts(self):
        md = format_to_markdown({
            "title": "T",
            "sections": [{"title": "Sec1", "content": "Body"}],
        })
        assert "## Sec1" in md
        assert "Body" in md

    def test_dict_with_glossary(self):
        md = format_to_markdown({
            "title": "T",
            "glossary": [
                {"term": "X", "explanation": "Y"},
                {"term": "Z"},
                "raw-string-item",
            ],
        })
        assert "**X**: Y" in md
        assert "- Z" in md
        assert "- raw-string-item" in md

    def test_geminiresult_full(self):
        result = GeminiResult(
            title="Manual",
            summary="概要テキスト",
            key_points=["p1", "p2"],
            sections=[Section(title="Sec", content="content")],
            glossary=[{"term": "API", "explanation": "Application Interface"}],
        )
        md = format_to_markdown(result)
        assert "# Manual" in md
        assert "## 概要" in md
        assert "## 重要ポイント" in md
        assert "- p1" in md
        assert "## Sec" in md
        assert "content" in md
        assert "## 用語集" in md
        assert "**API**: Application Interface" in md

    def test_dict_empty(self):
        # Empty dict: no title → falls through; implementation returns just default title prefix
        md = format_to_markdown({})
        assert isinstance(md, str)

    def test_geminiresult_none_title_summary(self):
        result = GeminiResult(
            title=None,
            summary=None,
            key_points=[],
            sections=[],
            glossary=[],
        )
        md = format_to_markdown(result)
        assert "マニュアル" in md

    def test_geminiresult_with_section_objects_only(self):
        section = Section(title="S", content="C")
        result = GeminiResult(
            title="T",
            summary="",
            key_points=[],
            sections=[section],
        )
        md = format_to_markdown(result)
        assert "## S" in md
        assert "C" in md
"""
Tests for Template System (Steps 23-34)
"""

import pytest
import tempfile
from pathlib import Path

from src.pdf_generator import TemplateLoader, TemplateLoadError, create_formatted_pdf
from src.docx_generator import DocxTemplateLoader, create_word_document


class TestPDFTemplateLoader:
    """PDF Template Loader tests"""

    def test_load_default_template(self):
        """Load default template"""
        template = TemplateLoader.load_template("default")
        assert template["name"] == "default"
        assert template["layout"] == "standard"
        assert "sections_order" in template

    def test_load_compact_template(self):
        """Load compact template"""
        template = TemplateLoader.load_template("compact")
        assert template["name"] == "compact"
        assert template["layout"] == "compact"
        assert template["parent"] == "default"

    def test_resolve_template_inheritance(self):
        """Test template inheritance resolution"""
        compact = TemplateLoader.load_template("compact")
        resolved = TemplateLoader.resolve_template(compact)

        assert resolved["name"] == "compact"
        assert "sections_order" in resolved
        assert resolved["title_font_size"] == 22

    def test_validate_template_valid(self):
        """Validate a valid template"""
        template = TemplateLoader.load_template("default")
        is_valid, msg = TemplateLoader.validate_template(template)
        assert is_valid is True
        assert msg == ""

    def test_validate_template_invalid_layout(self):
        """Validate template with invalid layout"""
        invalid = {"name": "test", "layout": "invalid", "sections_order": []}
        is_valid, msg = TemplateLoader.validate_template(invalid)
        assert is_valid is False
        assert "Invalid layout" in msg

    def test_validate_template_missing_field(self):
        """Validate template with missing required field"""
        invalid = {"name": "test", "layout": "standard"}
        is_valid, msg = TemplateLoader.validate_template(invalid)
        assert is_valid is False
        assert "sections_order" in msg

    def test_template_cache(self):
        """Test template caching"""
        TemplateLoader.clear_cache()

        t1 = TemplateLoader.load_template("default")
        t2 = TemplateLoader.load_template("default")
        assert t1 is t2

    def test_generate_pdf_with_template(self, tmp_path):
        """Generate PDF with template (ASCII content to avoid font issues)"""
        content = "Summary\nTest content summary\n\n## Key Points\n- Point 1\n- Point 2"
        output = tmp_path / "test.pdf"

        result = create_formatted_pdf(
            content,
            output,
            title="Test Document",
            template_name="compact"
        )

        assert result.exists()


class TestDocxTemplateLoader:
    """Word Document Template Loader tests"""

    def test_load_default_template(self):
        """Load default docx template"""
        template = DocxTemplateLoader.load_template("default")
        assert template["name"] == "default"
        assert template["layout"] == "standard"

    def test_load_compact_template(self):
        """Load compact docx template"""
        template = DocxTemplateLoader.load_template("compact")
        assert template["name"] == "compact"
        assert template["compact_mode"] is True

    def test_resolve_template(self):
        """Test template inheritance"""
        compact = DocxTemplateLoader.load_template("compact")
        resolved = DocxTemplateLoader.resolve_template(compact)

        assert resolved["layout"] == "compact"
        assert resolved["font_size"] == 13

    def test_validate_template(self):
        """Validate docx template"""
        template = DocxTemplateLoader.load_template("default")
        is_valid, msg = DocxTemplateLoader.validate_template(template)
        assert is_valid is True

    def test_generate_docx_with_template(self, tmp_path):
        """Generate Word document with template"""
        content = "概要\nテスト内容の要約\n\n## 重要ポイント\n- ポイント1\n- ポイント2"
        output = tmp_path / "test.docx"

        result = create_word_document(
            content,
            output,
            title="テストドキュメント",
            template_name="compact"
        )

        assert result.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

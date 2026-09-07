"""Tests for src/docx_generator.py"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


class TestDocxTemplateLoader:
    """Tests for DocxTemplateLoader"""

    def setup_method(self):
        from src.docx_generator import DocxTemplateLoader
        DocxTemplateLoader._cache.clear()

    def test_load_template_cache_hit(self):
        from src.docx_generator import DocxTemplateLoader

        DocxTemplateLoader._cache["test"] = {"name": "test"}
        result = DocxTemplateLoader.load_template("test")
        assert result == {"name": "test"}

    def test_load_template_file_not_found(self, tmp_path):
        from src.docx_generator import DocxTemplateLoader

        with patch('src.docx_generator.DOCX_TEMPLATE_DIR', tmp_path / "nonexistent"):
            DocxTemplateLoader._cache.clear()
            result = DocxTemplateLoader.load_template("nonexistent")
            defaults = DocxTemplateLoader._get_default_template()
            assert result == defaults

    def test_load_template_success(self, tmp_path):
        from src.docx_generator import DocxTemplateLoader

        template_file = tmp_path / "test_template.json"
        template_file.write_text(json.dumps({"name": "test", "layout": "compact"}))

        with patch('src.docx_generator.DOCX_TEMPLATE_DIR', tmp_path):
            result = DocxTemplateLoader.load_template("test_template")
            assert result["name"] == "test"
            assert result["layout"] == "compact"

    def test_load_template_json_error(self, tmp_path):
        from src.docx_generator import DocxTemplateLoader

        template_file = tmp_path / "bad_template.json"
        template_file.write_text("invalid json{")

        with patch('src.docx_generator.DOCX_TEMPLATE_DIR', tmp_path):
            result = DocxTemplateLoader.load_template("bad_template")
            defaults = DocxTemplateLoader._get_default_template()
            assert result == defaults

    def test_get_default_template(self):
        from src.docx_generator import DocxTemplateLoader

        result = DocxTemplateLoader._get_default_template()
        assert result["name"] == "default"
        assert result["layout"] == "standard"
        assert result["font_size"] == 11

    def test_resolve_template_no_parent(self):
        from src.docx_generator import DocxTemplateLoader

        template = {"name": "child", "layout": "compact"}
        result = DocxTemplateLoader.resolve_template(template)
        assert result["layout"] == "compact"

    def test_resolve_template_with_parent(self, tmp_path):
        from src.docx_generator import DocxTemplateLoader

        parent_file = tmp_path / "parent.json"
        parent_file.write_text(json.dumps({"name": "parent", "layout": "standard", "font_size": 11}))
        child_file = tmp_path / "child.json"
        child_file.write_text(json.dumps({"name": "child", "layout": "compact", "parent": "parent"}))

        with patch('src.docx_generator.DOCX_TEMPLATE_DIR', tmp_path):
            DocxTemplateLoader._cache.clear()
            result = DocxTemplateLoader.resolve_template({"name": "child", "layout": "compact", "parent": "parent"})
            assert result["layout"] == "compact"
            assert result["font_size"] == 11

    def test_validate_template_valid(self):
        from src.docx_generator import DocxTemplateLoader

        for layout in ["standard", "compact", "fancy"]:
            valid, msg = DocxTemplateLoader.validate_template({"layout": layout})
            assert valid is True

    def test_validate_template_invalid_layout(self):
        from src.docx_generator import DocxTemplateLoader

        valid, msg = DocxTemplateLoader.validate_template({"layout": "invalid"})
        assert valid is False
        assert "Invalid layout" in msg

    def test_validate_template_no_layout(self):
        from src.docx_generator import DocxTemplateLoader

        valid, msg = DocxTemplateLoader.validate_template({})
        assert valid is True

    def test_clear_cache(self):
        from src.docx_generator import DocxTemplateLoader

        DocxTemplateLoader._cache["test"] = {}
        DocxTemplateLoader.clear_cache()
        assert len(DocxTemplateLoader._cache) == 0


class TestWordGeneratorInit:
    """Tests for WordGenerator.__init__"""

    def test_init_success(self):
        with patch.dict('sys.modules', {'docx': MagicMock()}):
            with patch('src.docx_generator.Document', MagicMock()):
                from src.docx_generator import WordGenerator
                gen = WordGenerator()

    def test_init_without_docx(self):
        with patch.dict('sys.modules', {'docx': None}):
            with patch('src.docx_generator.Document', None):
                from src.docx_generator import WordGenerator
                with pytest.raises(ImportError):
                    WordGenerator()


class TestInsertDiagramImage:
    """Tests for insert_diagram_image()"""

    def test_skips_when_no_image(self):
        from src.docx_generator import WordGenerator
        gen = WordGenerator.__new__(WordGenerator)
        gen.insert_diagram_image(MagicMock(), Path("/nonexistent/image.png"))

    def test_inserts_valid_image(self, tmp_path):
        from src.docx_generator import WordGenerator
        from docx import Document

        img = tmp_path / "diagram.png"
        img.write_bytes(b"fake png data")

        mock_doc = MagicMock()
        gen = WordGenerator.__new__(WordGenerator)
        gen.insert_diagram_image(mock_doc, img)
        mock_doc.add_heading.assert_called_once()


class TestGenerateWord:
    """Tests for generate_word()"""

    def test_generate_basic_document(self, tmp_path):
        from src.docx_generator import WordGenerator

        output = tmp_path / "output.docx"
        gen = WordGenerator.__new__(WordGenerator)
        gen.insert_diagram_image = MagicMock()

        with patch('src.docx_generator.Document') as MockDocument:
            mock_doc = MagicMock()
            MockDocument.return_value = mock_doc

            result = gen.generate_word(
                "# Hello\n\nThis is content.",
                output,
                title="Test Doc"
            )
            assert result == output
            MockDocument.assert_called_once()

    def test_generate_with_template(self, tmp_path):
        from src.docx_generator import WordGenerator

        output = tmp_path / "output.docx"
        gen = WordGenerator.__new__(WordGenerator)
        gen.insert_diagram_image = MagicMock()

        with patch('src.docx_generator.Document') as MockDocument:
            mock_doc = MagicMock()
            MockDocument.return_value = mock_doc

            template = {
                "font_size": 13,
                "compact_mode": True,
                "emoji_enabled": True,
                "title_font_size": 20,
                "header_font_size": 16,
                "subheader_font_size": 14,
                "paragraph_spacing": 2,
                "line_spacing": 1.0
            }
            result = gen.generate_word("# Hello", output, template=template)
            assert result == output

    def test_generate_with_emoji(self, tmp_path):
        from src.docx_generator import WordGenerator

        output = tmp_path / "output.docx"
        gen = WordGenerator.__new__(WordGenerator)
        gen.insert_diagram_image = MagicMock()

        with patch('src.docx_generator.Document') as MockDocument:
            mock_doc = MagicMock()
            MockDocument.return_value = mock_doc

            result = gen.generate_word("# Hello", output, use_emojis=True)
            assert result == output

    def test_generate_with_qr_code(self, tmp_path):
        from src.docx_generator import WordGenerator

        output = tmp_path / "output.docx"
        qr = tmp_path / "qr.png"
        qr.write_bytes(b"fake")

        gen = WordGenerator.__new__(WordGenerator)
        gen.insert_diagram_image = MagicMock()

        with patch('src.docx_generator.Document') as MockDocument:
            mock_doc = MagicMock()
            MockDocument.return_value = mock_doc

            result = gen.generate_word("# Hello", output, qr_image_path=qr)
            assert result == output

    def test_generate_creates_parent_dir(self, tmp_path):
        from src.docx_generator import WordGenerator

        output = tmp_path / "subdir" / "output.docx"
        gen = WordGenerator.__new__(WordGenerator)
        gen.insert_diagram_image = MagicMock()

        with patch('src.docx_generator.Document') as MockDocument:
            mock_doc = MagicMock()
            MockDocument.return_value = mock_doc

            result = gen.generate_word("# Hello", output)
            assert (tmp_path / "subdir").exists()

    def test_generate_with_subsection_header_compact(self, tmp_path):
        from src.docx_generator import WordGenerator

        output = tmp_path / "output.docx"
        gen = WordGenerator.__new__(WordGenerator)
        gen.insert_diagram_image = MagicMock()

        with patch('src.docx_generator.Document') as MockDocument:
            mock_doc = MagicMock()
            MockDocument.return_value = mock_doc

            result = gen.generate_word("### SubSection", output, compact_layout=True)
            assert result == output

    def test_generate_with_bullet_compact(self, tmp_path):
        from src.docx_generator import WordGenerator

        output = tmp_path / "output.docx"
        gen = WordGenerator.__new__(WordGenerator)
        gen.insert_diagram_image = MagicMock()

        with patch('src.docx_generator.Document') as MockDocument:
            mock_doc = MagicMock()
            MockDocument.return_value = mock_doc

            result = gen.generate_word("- bullet item", output, compact_layout=True)
            assert result == output

    def test_generate_with_plain_paragraph_compact(self, tmp_path):
        from src.docx_generator import WordGenerator

        output = tmp_path / "output.docx"
        gen = WordGenerator.__new__(WordGenerator)
        gen.insert_diagram_image = MagicMock()

        with patch('src.docx_generator.Document') as MockDocument:
            mock_doc = MagicMock()
            MockDocument.return_value = mock_doc

            result = gen.generate_word("Plain paragraph text", output, compact_layout=True)
            assert result == output

    def test_generate_with_diagram_image(self, tmp_path):
        from src.docx_generator import WordGenerator

        output = tmp_path / "output.docx"
        diagram = tmp_path / "diagram.png"
        diagram.write_bytes(b"fake")

        gen = WordGenerator.__new__(WordGenerator)

        with patch('src.docx_generator.Document') as MockDocument:
            mock_doc = MagicMock()
            MockDocument.return_value = mock_doc

            result = gen.generate_word("# Hello", output, diagram_path=diagram)
            assert result == output


class TestCreateWordDocument:
    """Tests for create_word_document()"""

    def test_create_with_template_name(self, tmp_path):
        from src.docx_generator import create_word_document, DocxTemplateLoader

        DocxTemplateLoader._cache.clear()
        output = tmp_path / "output.docx"

        with patch('src.docx_generator.WordGenerator') as MockWG:
            mock_gen = MagicMock()
            MockWG.return_value = mock_gen

            result = create_word_document(
                "# Content",
                output,
                template_name="default"
            )
            mock_gen.generate_word.assert_called_once()

    def test_create_without_template(self, tmp_path):
        from src.docx_generator import create_word_document

        output = tmp_path / "output.docx"

        with patch('src.docx_generator.WordGenerator') as MockWG:
            mock_gen = MagicMock()
            MockWG.return_value = mock_gen

            result = create_word_document("# Content", output)
            mock_gen.generate_word.assert_called_once()

    def test_create_with_compact_layout(self, tmp_path):
        from src.docx_generator import create_word_document

        output = tmp_path / "output.docx"

        with patch('src.docx_generator.WordGenerator') as MockWG:
            mock_gen = MagicMock()
            MockWG.return_value = mock_gen

            result = create_word_document("# Content", output, compact_layout=True)
            call_kwargs = mock_gen.generate_word.call_args.kwargs
            assert call_kwargs.get("compact_layout") is True

    def test_create_with_diagram_path(self, tmp_path):
        from src.docx_generator import create_word_document

        output = tmp_path / "output.docx"
        diagram = tmp_path / "diagram.png"
        diagram.write_bytes(b"fake")

        with patch('src.docx_generator.WordGenerator') as MockWG:
            mock_gen = MagicMock()
            MockWG.return_value = mock_gen

            result = create_word_document("# Content", output, diagram_path=diagram)
            call_kwargs = mock_gen.generate_word.call_args.kwargs
            assert call_kwargs.get("diagram_path") == diagram

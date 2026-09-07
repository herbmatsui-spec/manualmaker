"""Tests for src/pdf_generator.py"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


class TestTemplateLoader:
    """Tests for TemplateLoader"""

    def setup_method(self):
        from src.pdf_generator import TemplateLoader
        TemplateLoader._cache.clear()

    def test_load_template_cache_hit(self):
        from src.pdf_generator import TemplateLoader

        TemplateLoader._cache["test"] = {"name": "test", "layout": "compact"}
        result = TemplateLoader.load_template("test")
        assert result == {"name": "test", "layout": "compact"}

    def test_load_template_file_not_found(self, tmp_path):
        from src.pdf_generator import TemplateLoader, TemplateLoadError

        with patch('src.pdf_generator.TEMPLATE_DIR', tmp_path):
            with pytest.raises(TemplateLoadError):
                TemplateLoader.load_template("nonexistent")

    def test_load_template_success(self, tmp_path):
        from src.pdf_generator import TemplateLoader

        template_file = tmp_path / "test.json"
        template_file.write_text(json.dumps({"name": "test", "layout": "compact", "sections_order": ["a"]}))

        with patch('src.pdf_generator.TEMPLATE_DIR', tmp_path):
            result = TemplateLoader.load_template("test")
            assert result["name"] == "test"
            assert result["layout"] == "compact"

    def test_load_template_json_error(self, tmp_path):
        from src.pdf_generator import TemplateLoader, TemplateLoadError

        template_file = tmp_path / "bad.json"
        template_file.write_text("invalid json{")

        with patch('src.pdf_generator.TEMPLATE_DIR', tmp_path):
            with pytest.raises(TemplateLoadError):
                TemplateLoader.load_template("bad")

    def test_resolve_template_no_parent(self):
        from src.pdf_generator import TemplateLoader

        template = {"name": "child", "layout": "compact", "sections_order": ["a"]}
        result = TemplateLoader.resolve_template(template)
        assert result["layout"] == "compact"

    def test_resolve_template_with_parent(self, tmp_path):
        from src.pdf_generator import TemplateLoader

        parent_file = tmp_path / "parent.json"
        parent_file.write_text(json.dumps({"name": "parent", "layout": "standard", "sections_order": ["a"]}))
        child_file = tmp_path / "child.json"
        child_file.write_text(json.dumps({"name": "child", "layout": "compact", "parent": "parent", "sections_order": ["a"]}))

        with patch('src.pdf_generator.TEMPLATE_DIR', tmp_path):
            TemplateLoader._cache.clear()
            result = TemplateLoader.resolve_template({"name": "child", "layout": "compact", "parent": "parent", "sections_order": ["a"]})
            assert result["layout"] == "compact"

    def test_validate_template_valid(self):
        from src.pdf_generator import TemplateLoader

        for layout in ["standard", "compact", "fancy"]:
            valid, _ = TemplateLoader.validate_template({
                "name": "test", "layout": layout, "sections_order": ["a", "b"]
            })
            assert valid is True

    def test_validate_template_missing_required(self):
        from src.pdf_generator import TemplateLoader

        valid, msg = TemplateLoader.validate_template({"name": "test"})
        assert valid is False
        assert "Missing required field" in msg

    def test_validate_template_sections_order_not_list(self):
        from src.pdf_generator import TemplateLoader

        valid, msg = TemplateLoader.validate_template({
            "name": "test", "layout": "standard", "sections_order": "not-a-list"
        })
        assert valid is False
        assert "sections_order must be a list" in msg

    def test_validate_template_invalid_layout(self):
        from src.pdf_generator import TemplateLoader

        valid, msg = TemplateLoader.validate_template({
            "name": "test", "layout": "invalid", "sections_order": ["a"]
        })
        assert valid is False
        assert "Invalid layout" in msg

    def test_clear_cache(self):
        from src.pdf_generator import TemplateLoader

        TemplateLoader._cache["test"] = {}
        TemplateLoader.clear_cache()
        assert len(TemplateLoader._cache) == 0


class TestPDFGeneratorInit:
    """Tests for PDFGenerator.__init__"""

    def test_init_success(self):
        with patch.dict('sys.modules', {'fpdf': MagicMock()}):
            with patch('src.pdf_generator.FPDF', MagicMock()):
                from src.pdf_generator import PDFGenerator
                gen = PDFGenerator()

    def test_init_without_fpdf(self):
        with patch.dict('sys.modules', {'fpdf': None}):
            with patch('src.pdf_generator.FPDF', None):
                from src.pdf_generator import PDFGenerator
                with pytest.raises(ImportError):
                    PDFGenerator()


class TestInsertDiagramImage:
    """Tests for insert_diagram_image()"""

    def test_skips_when_no_image(self):
        from src.pdf_generator import PDFGenerator
        gen = PDFGenerator.__new__(PDFGenerator)
        gen.insert_diagram_image(MagicMock(), Path("/nonexistent/image.png"))

    def test_inserts_valid_image(self, tmp_path):
        from src.pdf_generator import PDFGenerator

        img = tmp_path / "diagram.png"
        img.write_bytes(b"fake png data")

        mock_pdf = MagicMock()
        gen = PDFGenerator.__new__(PDFGenerator)
        gen.insert_diagram_image(mock_pdf, img)
        mock_pdf.add_page.assert_called_once()


class TestInsertQRImage:
    """Tests for insert_qr_image()"""

    def test_skips_when_no_image(self):
        from src.pdf_generator import PDFGenerator
        gen = PDFGenerator.__new__(PDFGenerator)
        gen.insert_qr_image(MagicMock(), Path("/nonexistent/qr.png"))

    def test_inserts_valid_image_with_jp_font(self, tmp_path):
        from src.pdf_generator import PDFGenerator

        img = tmp_path / "qr.png"
        img.write_bytes(b"fake png data")

        mock_pdf = MagicMock()
        gen = PDFGenerator.__new__(PDFGenerator)
        gen.insert_qr_image(mock_pdf, img, font_name="JPFont")
        mock_pdf.ln.assert_called()

    def test_inserts_valid_image_with_helvetica(self, tmp_path):
        from src.pdf_generator import PDFGenerator

        img = tmp_path / "qr.png"
        img.write_bytes(b"fake png data")

        mock_pdf = MagicMock()
        gen = PDFGenerator.__new__(PDFGenerator)
        gen.insert_qr_image(mock_pdf, img, font_name="Helvetica")
        mock_pdf.ln.assert_called()


class TestGeneratePDF:
    """Tests for generate_pdf()"""

    def test_generate_basic_pdf(self, tmp_path):
        from src.pdf_generator import PDFGenerator

        output = tmp_path / "output.pdf"
        gen = PDFGenerator.__new__(PDFGenerator)
        gen.insert_diagram_image = MagicMock()
        gen.insert_qr_image = MagicMock()

        with patch('src.pdf_generator.FPDF') as MockFPDF:
            mock_pdf = MagicMock()
            MockFPDF.return_value = mock_pdf

            result = gen.generate_pdf(
                "# Hello\n\nThis is content.",
                output,
                title="Test PDF"
            )
            assert result == output
            MockFPDF.assert_called_once()

    def test_generate_with_template(self, tmp_path):
        from src.pdf_generator import PDFGenerator

        output = tmp_path / "output.pdf"
        gen = PDFGenerator.__new__(PDFGenerator)
        gen.insert_diagram_image = MagicMock()
        gen.insert_qr_image = MagicMock()

        with patch('src.pdf_generator.FPDF') as MockFPDF:
            mock_pdf = MagicMock()
            MockFPDF.return_value = mock_pdf

            template = {
                "name": "test",
                "layout": "compact",
                "sections_order": ["a"],
                "font_size": 11,
                "margin": 12,
                "compact_mode": True,
                "emoji_enabled": True,
                "title_font_size": 22,
                "header_font_size": 16,
                "body_line_height": 6,
                "header_line_height": 8,
                "header_space_after": 2,
                "bullet_space_after": 1,
                "regular_space_after": 2
            }
            result = gen.generate_pdf("# Hello", output, template=template)
            assert result == output

    def test_generate_with_compact_layout(self, tmp_path):
        from src.pdf_generator import PDFGenerator

        output = tmp_path / "output.pdf"
        gen = PDFGenerator.__new__(PDFGenerator)
        gen.insert_diagram_image = MagicMock()
        gen.insert_qr_image = MagicMock()

        with patch('src.pdf_generator.FPDF') as MockFPDF:
            mock_pdf = MagicMock()
            MockFPDF.return_value = mock_pdf

            result = gen.generate_pdf("# Hello", output, compact_layout=True)
            assert result == output

    def test_generate_with_emoji(self, tmp_path):
        from src.pdf_generator import PDFGenerator

        output = tmp_path / "output.pdf"
        gen = PDFGenerator.__new__(PDFGenerator)
        gen.insert_diagram_image = MagicMock()
        gen.insert_qr_image = MagicMock()

        with patch('src.pdf_generator.FPDF') as MockFPDF:
            mock_pdf = MagicMock()
            MockFPDF.return_value = mock_pdf

            result = gen.generate_pdf("# Hello", output, use_emojis=True)
            assert result == output

    def test_generate_with_qr_code(self, tmp_path):
        from src.pdf_generator import PDFGenerator

        output = tmp_path / "output.pdf"
        qr = tmp_path / "qr.png"
        qr.write_bytes(b"fake")

        gen = PDFGenerator.__new__(PDFGenerator)
        gen.insert_diagram_image = MagicMock()
        gen.insert_qr_image = MagicMock()

        with patch('src.pdf_generator.FPDF') as MockFPDF:
            mock_pdf = MagicMock()
            MockFPDF.return_value = mock_pdf

            result = gen.generate_pdf("# Hello", output, qr_image_path=qr)
            assert result == output

    def test_generate_creates_parent_dir(self, tmp_path):
        from src.pdf_generator import PDFGenerator

        output = tmp_path / "subdir" / "output.pdf"
        gen = PDFGenerator.__new__(PDFGenerator)
        gen.insert_diagram_image = MagicMock()
        gen.insert_qr_image = MagicMock()

        with patch('src.pdf_generator.FPDF') as MockFPDF:
            mock_pdf = MagicMock()
            MockFPDF.return_value = mock_pdf

            result = gen.generate_pdf("# Hello", output)
            assert (tmp_path / "subdir").exists()

    def test_generate_with_diagram_image(self, tmp_path):
        from src.pdf_generator import PDFGenerator

        output = tmp_path / "output.pdf"
        diagram = tmp_path / "diagram.png"
        diagram.write_bytes(b"fake")

        gen = PDFGenerator.__new__(PDFGenerator)
        gen.insert_diagram_image = MagicMock()
        gen.insert_qr_image = MagicMock()

        with patch('src.pdf_generator.FPDF') as MockFPDF:
            mock_pdf = MagicMock()
            MockFPDF.return_value = mock_pdf

            result = gen.generate_pdf("# Hello", output, diagram_path=diagram)
            assert result == output

    def test_generate_with_section_headers(self, tmp_path):
        from src.pdf_generator import PDFGenerator

        output = tmp_path / "output.pdf"
        gen = PDFGenerator.__new__(PDFGenerator)
        gen.insert_diagram_image = MagicMock()
        gen.insert_qr_image = MagicMock()

        with patch('src.pdf_generator.FPDF') as MockFPDF:
            mock_pdf = MagicMock()
            MockFPDF.return_value = mock_pdf

            content = "## Section 1\n\nSome text\n- bullet item\n## Section 2"
            result = gen.generate_pdf(content, output)
            assert result == output

    def test_generate_with_bullets(self, tmp_path):
        from src.pdf_generator import PDFGenerator

        output = tmp_path / "output.pdf"
        gen = PDFGenerator.__new__(PDFGenerator)
        gen.insert_diagram_image = MagicMock()
        gen.insert_qr_image = MagicMock()

        with patch('src.pdf_generator.FPDF') as MockFPDF:
            mock_pdf = MagicMock()
            MockFPDF.return_value = mock_pdf

            content = "- item1\n- item2\n• item3"
            result = gen.generate_pdf(content, output)
            assert result == output

    def test_generate_skips_diagram_when_not_exists(self, tmp_path):
        from src.pdf_generator import PDFGenerator

        output = tmp_path / "output.pdf"
        gen = PDFGenerator.__new__(PDFGenerator)
        gen.insert_diagram_image = MagicMock()
        gen.insert_qr_image = MagicMock()

        with patch('src.pdf_generator.FPDF') as MockFPDF:
            mock_pdf = MagicMock()
            MockFPDF.return_value = mock_pdf

            result = gen.generate_pdf("# Hello", output, diagram_path=Path("/nonexistent/diagram.png"))
            assert result == output


class TestCreateFormattedPDF:
    """Tests for create_formatted_pdf()"""

    def test_create_with_template_name(self, tmp_path):
        from src.pdf_generator import create_formatted_pdf, TemplateLoader

        TemplateLoader._cache.clear()
        output = tmp_path / "output.pdf"

        with patch('src.pdf_generator.PDFGenerator') as MockPG:
            mock_gen = MagicMock()
            MockPG.return_value = mock_gen

            result = create_formatted_pdf("# Content", output, template_name="default")
            mock_gen.generate_pdf.assert_called_once()

    def test_create_without_template(self, tmp_path):
        from src.pdf_generator import create_formatted_pdf

        output = tmp_path / "output.pdf"

        with patch('src.pdf_generator.PDFGenerator') as MockPG:
            mock_gen = MagicMock()
            MockPG.return_value = mock_gen

            result = create_formatted_pdf("# Content", output)
            mock_gen.generate_pdf.assert_called_once()

    def test_create_with_compact_layout(self, tmp_path):
        from src.pdf_generator import create_formatted_pdf

        output = tmp_path / "output.pdf"

        with patch('src.pdf_generator.PDFGenerator') as MockPG:
            mock_gen = MagicMock()
            MockPG.return_value = mock_gen

            result = create_formatted_pdf("# Content", output, compact_layout=True)
            call_kwargs = mock_gen.generate_pdf.call_args.kwargs
            assert call_kwargs.get("compact_layout") is True

    def test_create_with_diagram_path(self, tmp_path):
        from src.pdf_generator import create_formatted_pdf

        output = tmp_path / "output.pdf"
        diagram = tmp_path / "diagram.png"
        diagram.write_bytes(b"fake")

        with patch('src.pdf_generator.PDFGenerator') as MockPG:
            mock_gen = MagicMock()
            MockPG.return_value = mock_gen

            result = create_formatted_pdf("# Content", output, diagram_path=diagram)
            call_kwargs = mock_gen.generate_pdf.call_args.kwargs
            assert call_kwargs.get("diagram_path") == diagram

    def test_create_template_load_error(self, tmp_path):
        from src.pdf_generator import create_formatted_pdf, TemplateLoader, TemplateLoadError

        TemplateLoader._cache.clear()
        output = tmp_path / "output.pdf"

        with patch('src.pdf_generator.TEMPLATE_DIR', tmp_path):
            with patch('src.pdf_generator.PDFGenerator') as MockPG:
                mock_gen = MagicMock()
                MockPG.return_value = mock_gen

                result = create_formatted_pdf("# Content", output, template_name="nonexistent")
                mock_gen.generate_pdf.assert_called_once()

    def test_create_template_validation_error(self, tmp_path, monkeypatch):
        from src.pdf_generator import create_formatted_pdf, TemplateLoader

        TemplateLoader._cache.clear()
        output = tmp_path / "output.pdf"

        template_file = tmp_path / "invalid.json"
        template_file.write_text(json.dumps({"name": "test", "sections_order": "not-a-list"}))

        with patch('src.pdf_generator.TEMPLATE_DIR', tmp_path):
            with patch('src.pdf_generator.PDFGenerator') as MockPG:
                mock_gen = MagicMock()
                MockPG.return_value = mock_gen

                result = create_formatted_pdf("# Content", output, template_name="invalid")
                mock_gen.generate_pdf.assert_called_once()

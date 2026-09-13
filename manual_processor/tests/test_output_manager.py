"""Tests for src/output_manager.py"""

import sys
import importlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

src_path = Path(__file__).resolve().parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from src.output_manager import (
    OutputFiles,
    OutputConfig,
    save_all_formats,
    save_single_format,
    _extract_audio_text,
)
from src.gemini_processor import GeminiResult
from src.models import Section


class TestExtractAudioText:
    def test_key_points_first(self):
        content = MagicMock(key_points=["a", "b"], summary="S")
        assert _extract_audio_text(content, "fmt") == "a\nb"

    def test_summary_when_no_key_points(self):
        content = MagicMock(key_points=None, summary="S")
        assert _extract_audio_text(content, "fmt") == "S"

    def test_fallback_to_formatted_text(self):
        content = MagicMock(spec=[])  # no attributes
        assert _extract_audio_text(content, "fmt") == "fmt"


class TestSaveAllFormats:
    def test_save_all_formats_skips_optional_outputs(self, tmp_path):
        content = GeminiResult(
            title="T",
            summary="S",
            key_points=["p"],
            sections=[Section(title="Sec", content="c")],
        )
        cfg = OutputConfig(
            output_directory=tmp_path,
            base_name="out",
            include_pdf=False,
            include_docx=False,
            include_audio=False,
            include_qr=False,
        )

        with patch("src.output_manager.format_to_markdown", return_value="# T\nS"), \
             patch("src.output_manager.create_formatted_pdf") as pdf_mock, \
             patch("src.output_manager.create_word_document") as docx_mock, \
             patch("src.output_manager.AudioGenerator") as audio_mock:
            result = save_all_formats(content, Path("in.pdf"), cfg)

        assert isinstance(result, OutputFiles)
        assert result.metadata["errors"] == []
        assert result.metadata["page_count"] == 1
        assert result.metadata["word_count"] == 1
        assert result.metadata["key_point_count"] == 1
        assert result.metadata["drive_urls"] == {}
        pdf_mock.assert_not_called()
        docx_mock.assert_not_called()
        audio_mock.assert_not_called()

    def test_save_all_formats_handles_audio_pdf_docx_errors(self, tmp_path):
        from src.exceptions import TTSError, PDFGenerationError, DocxGenerationError

        content = GeminiResult(title="T", summary="S", key_points=[], sections=[])
        cfg = OutputConfig(
            output_directory=tmp_path,
            base_name="out",
            include_pdf=True,
            include_docx=True,
            include_audio=True,
            include_qr=False,
        )

        with patch("src.output_manager.format_to_markdown", return_value="md"), \
             patch("src.output_manager.AudioGenerator") as audio_mod, \
             patch("src.output_manager.create_formatted_pdf",
                   side_effect=PDFGenerationError("pdf boom")), \
             patch("src.output_manager.create_word_document",
                   side_effect=DocxGenerationError("docx boom")):
            audio_mod.return_value.generate_audio.side_effect = TTSError("audio boom")
            result = save_all_formats(content, Path("in.pdf"), cfg)

        errors = result.metadata["errors"]
        assert any("Audio" in e for e in errors)
        assert any("PDF" in e for e in errors)
        assert any("Word" in e for e in errors)

    def test_save_all_formats_qr_generation_failure_continues(self, tmp_path):
        from src.qr_generator import QRCodeError

        content = GeminiResult(title="T", summary="S", key_points=[], sections=[])
        cfg = OutputConfig(
            output_directory=tmp_path,
            base_name="out",
            include_pdf=False,
            include_docx=False,
            include_audio=False,
            include_qr=True,
        )

        with patch("src.output_manager.format_to_markdown", return_value="md"), \
             patch("src.output_manager.QRGenerator") as qr_mod:
            qr_mod.return_value.generate_qr.side_effect = QRCodeError("qr boom")
            result = save_all_formats(content, Path("in.pdf"), cfg, file_id="fid")

        assert result.qr_path is None

    def test_save_all_formats_qr_unexpected_error(self, tmp_path):
        content = GeminiResult(title="T", summary="S", key_points=[], sections=[])
        cfg = OutputConfig(
            output_directory=tmp_path,
            base_name="out",
            include_pdf=False,
            include_docx=False,
            include_audio=False,
            include_qr=True,
        )

        with patch("src.output_manager.format_to_markdown", return_value="md"), \
             patch("src.output_manager.QRGenerator") as qr_mod:
            qr_mod.return_value.generate_qr.side_effect = RuntimeError("unexpected")
            result = save_all_formats(content, Path("in.pdf"), cfg, file_id="fid")

        assert result.qr_path is None

    def test_save_all_formats_drive_upload_when_include_drive(self, tmp_path):
        content = GeminiResult(title="T", summary="S", key_points=[], sections=[])
        cfg = OutputConfig(
            output_directory=tmp_path,
            base_name="out",
            include_pdf=False,
            include_docx=False,
            include_audio=False,
            include_qr=False,
            include_drive=True,
        )

        fake_drive_module = MagicMock()
        fake_drive_module.GoogleDriveManager.return_value.is_authenticated.return_value = False
        fake_drive_module.GoogleDriveError = Exception

        with patch("src.output_manager.format_to_markdown", return_value="md"), \
             patch.dict("sys.modules", {"src.google_drive_manager": fake_drive_module}):
            result = save_all_formats(content, Path("in.pdf"), cfg)

        assert result.metadata["drive_urls"] == {}

    def test_save_all_formats_drive_import_error(self, tmp_path):
        content = GeminiResult(title="T", summary="S", key_points=[], sections=[])
        cfg = OutputConfig(
            output_directory=tmp_path,
            base_name="out",
            include_pdf=False,
            include_docx=False,
            include_audio=False,
            include_qr=False,
            include_drive=True,
        )

        with patch("src.output_manager.format_to_markdown", return_value="md"), \
             patch.dict("sys.modules", {"src.google_drive_manager": None}):
            # ImportError should be swallowed
            result = save_all_formats(content, Path("in.pdf"), cfg)

        assert result.metadata["drive_urls"] == {}

    def test_save_all_formats_unexpected_drive_error(self, tmp_path):
        content = GeminiResult(title="T", summary="S", key_points=[], sections=[])
        cfg = OutputConfig(
            output_directory=tmp_path,
            base_name="out",
            include_pdf=False,
            include_docx=False,
            include_audio=False,
            include_qr=False,
            include_drive=True,
        )

        fake_drive_module = MagicMock()
        fake_drive_module.GoogleDriveManager.side_effect = RuntimeError("boom")
        fake_drive_module.GoogleDriveError = Exception

        with patch("src.output_manager.format_to_markdown", return_value="md"), \
             patch.dict("sys.modules", {"src.google_drive_manager": fake_drive_module}):
            result = save_all_formats(content, Path("in.pdf"), cfg)

        assert result.metadata["drive_urls"] == {}

    def test_save_all_formats_uses_base_output_path_stem_when_base_name_empty(self, tmp_path):
        content = GeminiResult(title="T", summary="S", key_points=[], sections=[])
        cfg = OutputConfig(
            output_directory=tmp_path,
            base_name="",
            include_pdf=False,
            include_docx=False,
            include_audio=False,
            include_qr=False,
        )

        with patch("src.output_manager.format_to_markdown", return_value="md"):
            result = save_all_formats(content, Path("my-manual.pdf"), cfg)

        assert result.pdf_path.name == "my-manual.pdf"
        assert result.docx_path.name == "my-manual.docx"
        assert result.audio_path.name == "my-manual.mp3"


class TestSaveSingleFormat:
    def test_pdf(self, tmp_path):
        content = GeminiResult(title="T", summary="S", key_points=[], sections=[])
        out = tmp_path / "x.pdf"
        with patch("src.output_manager.format_to_markdown", return_value="md"), \
             patch("src.output_manager.create_formatted_pdf", return_value=out) as pdf:
            result = save_single_format(content, out, "pdf")
        assert result == out
        pdf.assert_called_once()

    def test_docx(self, tmp_path):
        content = GeminiResult(title="T", summary="S", key_points=[], sections=[])
        out = tmp_path / "x.docx"
        with patch("src.output_manager.format_to_markdown", return_value="md"), \
             patch("src.output_manager.create_word_document", return_value=out) as docx:
            result = save_single_format(content, out, "docx")
        assert result == out
        docx.assert_called_once()

    def test_audio(self, tmp_path):
        content = GeminiResult(title="T", summary="S", key_points=[], sections=[])
        out = tmp_path / "x.mp3"
        with patch("src.output_manager.format_to_markdown", return_value="md"), \
             patch("src.output_manager.AudioGenerator") as audio_mod:
            audio_mod.return_value.generate_audio.return_value = out
            result = save_single_format(content, out, "audio")
        assert result == out

    def test_diagram_markdown(self, tmp_path):
        out = tmp_path / "x.md"
        fake_inst = MagicMock()
        fake_inst.save_as_markdown.return_value = out

        # Create a real subclass that overrides __new__ to return our fake_inst.
        class FakeDiagramGenerator:
            def __new__(cls, *args, **kwargs):
                return fake_inst

        fake_mod = MagicMock()
        fake_mod.DiagramGenerator = FakeDiagramGenerator

        with patch("src.output_manager.format_to_markdown", return_value="md"), \
             patch.dict("sys.modules", {"src.diagram_generator": fake_mod}):
            result = save_single_format("flowchart code", out, "diagram_markdown")
        assert result == out
        fake_inst.save_as_markdown.assert_called_once()

    def test_diagram_mermaid(self, tmp_path):
        out = tmp_path / "x.mmd"
        fake_inst = MagicMock()
        fake_inst.save_as_mermaid.return_value = out

        class FakeDiagramGenerator:
            def __new__(cls, *args, **kwargs):
                return fake_inst

        fake_mod = MagicMock()
        fake_mod.DiagramGenerator = FakeDiagramGenerator

        with patch("src.output_manager.format_to_markdown", return_value="md"), \
             patch.dict("sys.modules", {"src.diagram_generator": fake_mod}):
            result = save_single_format("flowchart code", out, "diagram_mermaid")
        assert result == out
        fake_inst.save_as_mermaid.assert_called_once()

    def test_diagram_markdown_falls_back_to_attr(self, tmp_path):
        out = tmp_path / "x.md"
        content = MagicMock()
        content.mermaid_code = "from-attr"
        fake_inst = MagicMock()
        fake_inst.save_as_markdown.return_value = out

        class FakeDiagramGenerator:
            def __new__(cls, *args, **kwargs):
                return fake_inst

        fake_mod = MagicMock()
        fake_mod.DiagramGenerator = FakeDiagramGenerator

        with patch("src.output_manager.format_to_markdown", return_value="md"), \
             patch.dict("sys.modules", {"src.diagram_generator": fake_mod}):
            save_single_format(content, out, "diagram_markdown")
        fake_inst.save_as_markdown.assert_called_once()

    def test_unsupported_format_raises(self, tmp_path):
        content = GeminiResult(title="T", summary="S", key_points=[], sections=[])
        with patch("src.output_manager.format_to_markdown", return_value="md"):
            with pytest.raises(ValueError):
                save_single_format(content, tmp_path / "x.bin", "unknown")


class TestSaveAllFormatsCoverageStep7:
    """Step 7: output_manager.py 未到達行のカバレッジテスト"""

    def _make_content(self):
        return GeminiResult(title="T", summary="S", key_points=["k"], sections=[])

    # ---------- L85, L102, L114, L126: 各生成の成功ログ ----------
    def test_save_all_formats_success_all_outputs(self, tmp_path):
        content = self._make_content()
        qr_path = tmp_path / "out_qr.png"
        pdf_path = tmp_path / "out.pdf"
        docx_path = tmp_path / "out.docx"
        audio_path = tmp_path / "out.mp3"

        cfg = OutputConfig(
            output_directory=tmp_path,
            base_name="out",
            include_pdf=True,
            include_docx=True,
            include_audio=True,
            include_qr=True,
        )

        with patch("src.output_manager.format_to_markdown", return_value="md"), \
             patch("src.output_manager.QRGenerator") as qr_mod, \
             patch("src.output_manager.AudioGenerator") as audio_mod, \
             patch("src.output_manager.create_formatted_pdf", return_value=pdf_path), \
             patch("src.output_manager.create_word_document", return_value=docx_path):
            qr_mod.return_value.generate_qr.return_value = qr_path
            audio_mod.return_value.generate_audio.return_value = audio_path
            result = save_all_formats(content, Path("in.pdf"), cfg, file_id="fid")

        assert result.qr_path == qr_path
        assert result.pdf_path == pdf_path
        assert result.docx_path == docx_path
        assert result.audio_path == audio_path
        assert result.metadata["errors"] == []

    # ---------- L106-108, L118-120, L130-132: 予期せぬ例外 ----------
    def test_save_all_formats_unexpected_errors_recorded(self, tmp_path):
        content = self._make_content()
        cfg = OutputConfig(
            output_directory=tmp_path,
            base_name="out",
            include_pdf=True,
            include_docx=True,
            include_audio=True,
            include_qr=False,
        )

        with patch("src.output_manager.format_to_markdown", return_value="md"), \
             patch("src.output_manager.AudioGenerator") as audio_mod, \
             patch("src.output_manager.create_formatted_pdf",
                   side_effect=RuntimeError("pdf unexpected")), \
             patch("src.output_manager.create_word_document",
                   side_effect=RuntimeError("docx unexpected")):
            audio_mod.return_value.generate_audio.side_effect = RuntimeError("audio unexpected")
            result = save_all_formats(content, Path("in.pdf"), cfg)

        errors = result.metadata["errors"]
        assert any("Audio" in e and "audio unexpected" in e for e in errors)
        assert any("PDF" in e and "pdf unexpected" in e for e in errors)
        assert any("Word" in e and "docx unexpected" in e for e in errors)

    # ---------- L155-186: Drive アップロード成功系 ----------
    def test_save_all_formats_drive_upload_authenticated(self, tmp_path):
        content = self._make_content()
        pdf_path = tmp_path / "out.pdf"
        docx_path = tmp_path / "out.docx"
        audio_path = tmp_path / "out.mp3"
        for p in (pdf_path, docx_path, audio_path):
            p.write_bytes(b"dummy")

        cfg = OutputConfig(
            output_directory=tmp_path,
            base_name="out",
            include_pdf=True,
            include_docx=True,
            include_audio=True,
            include_qr=False,
            include_drive=True,
            drive_folder_id="folder_123",
        )

        fake_drive_file = MagicMock()
        fake_drive_file.file_id = "drive_file_1"
        fake_drive_file.web_view_link = "https://drive.google.com/view"
        fake_drive_file.web_content_link = "https://drive.google.com/content"

        fake_drive_module = MagicMock()
        mock_manager = fake_drive_module.GoogleDriveManager.return_value
        mock_manager.is_authenticated.return_value = True
        mock_manager.upload_and_share.return_value = fake_drive_file
        fake_drive_module.GoogleDriveError = Exception

        with patch("src.output_manager.format_to_markdown", return_value="md"), \
             patch("src.output_manager.create_formatted_pdf", return_value=pdf_path), \
             patch("src.output_manager.create_word_document", return_value=docx_path), \
             patch("src.output_manager.AudioGenerator") as audio_mod, \
             patch.dict("sys.modules", {"src.google_drive_manager": fake_drive_module}):
            audio_mod.return_value.generate_audio.return_value = audio_path
            result = save_all_formats(content, Path("in.pdf"), cfg)

        drive_urls = result.metadata["drive_urls"]
        assert set(drive_urls.keys()) == {"pdf", "docx", "audio"}
        for entry in drive_urls.values():
            assert entry["file_id"] == "drive_file_1"
        assert mock_manager.upload_and_share.call_count == 3

    # ---------- L158: フォルダ作成 (drive_folder_name 経由) ----------
    def test_save_all_formats_drive_folder_created_from_name(self, tmp_path):
        content = self._make_content()
        pdf_path = tmp_path / "out.pdf"
        pdf_path.write_bytes(b"dummy")

        cfg = OutputConfig(
            output_directory=tmp_path,
            base_name="out",
            include_pdf=True,
            include_docx=False,
            include_audio=False,
            include_qr=False,
            include_drive=True,
            drive_folder_id=None,
        )
        cfg.drive_folder_name = "TestFolder"

        fake_drive_file = MagicMock()
        fake_drive_file.file_id = "drive_file_2"
        fake_drive_file.web_view_link = "https://drive.google.com/view"
        fake_drive_file.web_content_link = "https://drive.google.com/content"

        fake_drive_module = MagicMock()
        mock_manager = fake_drive_module.GoogleDriveManager.return_value
        mock_manager.is_authenticated.return_value = True
        mock_manager.create_folder.return_value = "created_folder_id"
        mock_manager.upload_and_share.return_value = fake_drive_file
        fake_drive_module.GoogleDriveError = Exception

        with patch("src.output_manager.format_to_markdown", return_value="md"), \
             patch("src.output_manager.create_formatted_pdf", return_value=pdf_path), \
             patch.dict("sys.modules", {"src.google_drive_manager": fake_drive_module}):
            result = save_all_formats(content, Path("in.pdf"), cfg)

        mock_manager.create_folder.assert_called_once_with("TestFolder")
        assert result.metadata["drive_urls"]["pdf"]["file_id"] == "drive_file_2"
        _, kwargs = mock_manager.upload_and_share.call_args
        assert kwargs["folder_id"] == "created_folder_id"

    # ---------- L159-160: フォルダ作成失敗時の警告 ----------
    def test_save_all_formats_drive_folder_creation_error(self, tmp_path):
        content = self._make_content()
        pdf_path = tmp_path / "out.pdf"
        pdf_path.write_bytes(b"dummy")

        cfg = OutputConfig(
            output_directory=tmp_path,
            base_name="out",
            include_pdf=True,
            include_docx=False,
            include_audio=False,
            include_qr=False,
            include_drive=True,
            drive_folder_id=None,
        )
        cfg.drive_folder_name = "TestFolder"

        fake_drive_file = MagicMock()
        fake_drive_file.file_id = "drive_file_3"
        fake_drive_file.web_view_link = "https://drive.google.com/view"
        fake_drive_file.web_content_link = "https://drive.google.com/content"

        fake_drive_module = MagicMock()
        mock_manager = fake_drive_module.GoogleDriveManager.return_value
        mock_manager.is_authenticated.return_value = True
        mock_manager.create_folder.side_effect = Exception("Folder failed")
        mock_manager.upload_and_share.return_value = fake_drive_file
        fake_drive_module.GoogleDriveError = Exception

        with patch("src.output_manager.format_to_markdown", return_value="md"), \
             patch("src.output_manager.create_formatted_pdf", return_value=pdf_path), \
             patch.dict("sys.modules", {"src.google_drive_manager": fake_drive_module}):
            result = save_all_formats(content, Path("in.pdf"), cfg)

        # フォルダ作成失敗してもアップロードは続行 (folder_id=None)
        assert result.metadata["drive_urls"]["pdf"]["file_id"] == "drive_file_3"
        _, kwargs = mock_manager.upload_and_share.call_args
        assert kwargs["folder_id"] is None

    # ---------- L184-186: アップロード失敗時の警告 ----------
    def test_save_all_formats_drive_upload_per_file_error(self, tmp_path):
        content = self._make_content()
        pdf_path = tmp_path / "out.pdf"
        pdf_path.write_bytes(b"dummy")

        cfg = OutputConfig(
            output_directory=tmp_path,
            base_name="out",
            include_pdf=True,
            include_docx=False,
            include_audio=False,
            include_qr=False,
            include_drive=True,
            drive_folder_id="folder_123",
        )

        fake_drive_module = MagicMock()
        mock_manager = fake_drive_module.GoogleDriveManager.return_value
        mock_manager.is_authenticated.return_value = True
        mock_manager.upload_and_share.side_effect = Exception("Upload failed")
        fake_drive_module.GoogleDriveError = Exception

        with patch("src.output_manager.format_to_markdown", return_value="md"), \
             patch("src.output_manager.create_formatted_pdf", return_value=pdf_path), \
             patch.dict("sys.modules", {"src.google_drive_manager": fake_drive_module}):
            result = save_all_formats(content, Path("in.pdf"), cfg)

        assert result.metadata["drive_urls"]["pdf"] == {"error": "Upload failed"}
"""diagram_generator.py のユニットテスト"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from src.diagram_generator import DiagramGenerator, DiagramResult
from src.exceptions import DiagramGenerationError


class TestDiagramGeneratorInit:
    """DiagramGenerator.__init__ tests"""

    def test_init_with_genai_client(self):
        with patch.dict('sys.modules', {'google': MagicMock(), 'google.genai': MagicMock()}):
            with patch('src.diagram_generator._HAS_GENAI', True):
                with patch('src.diagram_generator.genai.Client') as mock_client:
                    gen = DiagramGenerator("test-key", "gemini-model")
                    assert gen.api_key == "test-key"
                    assert gen.model_name == "gemini-model"
                    mock_client.assert_called_once_with(api_key="test-key")

    def test_init_without_genai_client(self):
        pass


class TestRenderToImage:
    """render_to_image() tests"""

    def test_render_with_mermaidx_render(self, tmp_path):
        output = tmp_path / "diagram.png"
        gen = DiagramGenerator.__new__(DiagramGenerator)
        mock_render = MagicMock()
        mock_mermaidx = MagicMock()
        mock_mermaidx.render = mock_render
        with patch.dict('sys.modules', {'mermaidx': mock_mermaidx}):
            result = gen.render_to_image("flowchart TD\nA-->B", output)
        assert result == output
        mock_render.assert_called_once()

    def test_render_with_mermaid_class(self, tmp_path):
        output = tmp_path / "diagram.png"
        gen = DiagramGenerator.__new__(DiagramGenerator)
        mock_mermaid = MagicMock()
        mock_mermaid_instance = MagicMock()
        mock_mermaid.return_value = mock_mermaid_instance
        mock_mermaidx = MagicMock()
        mock_mermaidx.render.side_effect = ImportError()
        mock_mermaidx.Mermaid = mock_mermaid
        with patch.dict('sys.modules', {'mermaidx': mock_mermaidx}):
            result = gen.render_to_image("flowchart TD\nA-->B", output)
        assert result == output
        mock_mermaid_instance.to_png.assert_called_once()

    def test_render_with_mmdc_cli_success(self, tmp_path):
        output = tmp_path / "diagram.png"
        gen = DiagramGenerator.__new__(DiagramGenerator)
        mock_mermaidx = MagicMock()
        mock_mermaidx.render.side_effect = ImportError()
        mock_mermaidx.Mermaid.side_effect = AttributeError()
        with patch.dict('sys.modules', {'mermaidx': mock_mermaidx}):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stderr="")
                result = gen.render_to_image("flowchart TD\nA-->B", output)
                assert result == output
                mock_run.assert_called_once()

    def test_render_with_mmdc_cli_failure(self, tmp_path):
        output = tmp_path / "diagram.png"
        gen = DiagramGenerator.__new__(DiagramGenerator)
        mock_mermaidx = MagicMock()
        mock_mermaidx.render.side_effect = ImportError()
        mock_mermaidx.Mermaid.side_effect = AttributeError()
        with patch.dict('sys.modules', {'mermaidx': mock_mermaidx}):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(returncode=1, stderr="mmdc error")
                with pytest.raises(DiagramGenerationError):
                    gen.render_to_image("flowchart TD\nA-->B", output)


class TestGenerateMermaidCode:
    """generate_mermaid_code() tests"""

    def test_generate_with_genai_client(self):
        with patch.dict('sys.modules', {'google': MagicMock(), 'google.genai': MagicMock()}):
            with patch('src.diagram_generator._HAS_GENAI', True):
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.text = "```\nflowchart TD\n    A --> B\n```"
                mock_client.models.generate_content.return_value = mock_response

                gen = DiagramGenerator.__new__(DiagramGenerator)
                gen.client = mock_client
                gen.model_name = "test-model"

                result = gen.generate_mermaid_code("text", [{"title": "t", "content": "c"}], ["kp"])
                assert "flowchart TD" in result
                assert "A" in result

    def test_generate_with_legacy_genai(self):
        with patch.dict('sys.modules', {'google': MagicMock(), 'google.genai': MagicMock(), 'google.generativeai': MagicMock()}):
            with patch('src.diagram_generator._HAS_GENAI', False):
                mock_model = MagicMock()
                mock_response = MagicMock()
                mock_response.text = "flowchart TD\n    A --> B"
                mock_model.generate_content.return_value = mock_response

                gen = DiagramGenerator.__new__(DiagramGenerator)
                gen.model = mock_model

                result = gen.generate_mermaid_code("text", [{"title": "t", "content": "c"}], ["kp"])
                assert "flowchart TD" in result

    def test_generate_strips_code_fences(self):
        with patch.dict('sys.modules', {'google': MagicMock(), 'google.genai': MagicMock()}):
            with patch('src.diagram_generator._HAS_GENAI', True):
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.text = "```mermaid\nflowchart TD\nA-->B\n```"
                mock_client.models.generate_content.return_value = mock_response

                gen = DiagramGenerator.__new__(DiagramGenerator)
                gen.client = mock_client
                gen.model_name = "test-model"

                result = gen.generate_mermaid_code("text", [], [])
                assert result.startswith("flowchart TD")
                assert "```" not in result

    def test_generate_raises_exception(self):
        with patch.dict('sys.modules', {'google': MagicMock(), 'google.genai': MagicMock()}):
            with patch('src.diagram_generator._HAS_GENAI', True):
                mock_client = MagicMock()
                mock_client.models.generate_content.side_effect = RuntimeError("API error")

                gen = DiagramGenerator.__new__(DiagramGenerator)
                gen.client = mock_client
                gen.model_name = "test-model"

                with pytest.raises(RuntimeError):
                    gen.generate_mermaid_code("text", [], [])


class TestGenerate:
    """generate() method tests"""

    def test_generate_uses_fallback_when_mermaid_code_fails(self, tmp_path):
        gen = DiagramGenerator.__new__(DiagramGenerator)
        gen.generate_mermaid_code = MagicMock(side_effect=RuntimeError("API fail"))
        gen.validate_mermaid_code = lambda c: (True, "")
        gen.render_to_image = MagicMock(side_effect=DiagramGenerationError("render fail"))

        result = gen.generate(
            "text",
            [{"title": "Step 1", "content": "desc"}],
            [],
            output_path=tmp_path / "out.png"
        )
        assert result.success is True
        assert result.diagram_type == "flowchart_fallback"

    def test_generate_with_invalid_mermaid_repaired(self, tmp_path):
        gen = DiagramGenerator.__new__(DiagramGenerator)
        gen.generate_mermaid_code = MagicMock(return_value="invalid code")
        gen.validate_mermaid_code = lambda c: (False, "invalid") if "invalid" in c else (True, "")
        gen.repair_mermaid_code = lambda c: "flowchart TD\nA-->B"
        gen.render_to_image = lambda *a, **k: tmp_path / "out.png"

        result = gen.generate(
            "text", [], [],
            output_path=tmp_path / "out.png"
        )
        assert result.success is True
        assert result.mermaid_code == "flowchart TD\nA-->B"

    def test_generate_returns_markdown_and_mermaid_only(self, tmp_path):
        gen = DiagramGenerator.__new__(DiagramGenerator)
        gen.generate_mermaid_code = MagicMock(return_value="flowchart TD\nA-->B")
        gen.validate_mermaid_code = lambda c: (True, "")
        gen.render_to_image = MagicMock(side_effect=DiagramGenerationError("fail"))
        gen._create_fallback_image = MagicMock(side_effect=Exception("fallback failed"))

        result = gen.generate(
            "text", [], [],
            output_path=tmp_path / "out.png",
            markdown_path=tmp_path / "out.md",
            mermaid_path=tmp_path / "out.mmd"
        )
        assert result.success is True
        assert result.image_path is None
        assert result.mermaid_path is not None
        assert result.markdown_path is not None


class TestBuildSimpleFlowchart:
    """_build_simple_flowchart tests"""

    def test_build_with_empty_sections(self):
        gen = DiagramGenerator.__new__(DiagramGenerator)
        result = gen._build_simple_flowchart([], [])
        assert "flowchart TD" in result
        assert "開始" in result

    def test_build_with_key_points_only(self):
        gen = DiagramGenerator.__new__(DiagramGenerator)
        result = gen._build_simple_flowchart([], ["point1", "point2"])
        assert "flowchart TD" in result
        assert "point1" in result

    def test_build_truncates_long_labels(self):
        gen = DiagramGenerator.__new__(DiagramGenerator)
        long_title = "A" * 100
        result = gen._build_simple_flowchart([{"title": long_title, "content": ""}], [])
        assert len(result.split('\n')) <= 15


class TestMermaidValidation:
    """Mermaid コードバリデーションのテスト"""

    def test_valid_flowchart(self):
        is_valid, msg = DiagramGenerator.validate_mermaid_code(
            "flowchart TD\n    A[開始] --> B[終了]"
        )
        assert is_valid is True

    def test_empty_code(self):
        is_valid, msg = DiagramGenerator.validate_mermaid_code("")
        assert is_valid is False
        assert "空" in msg

    def test_invalid_start(self):
        is_valid, msg = DiagramGenerator.validate_mermaid_code("hello world")
        assert is_valid is False

    def test_no_nodes(self):
        is_valid, msg = DiagramGenerator.validate_mermaid_code("flowchart TD\n")
        assert is_valid is False

    def test_valid_graph_td(self):
        is_valid, _ = DiagramGenerator.validate_mermaid_code("graph TD\nA-->B")
        assert is_valid is True

    def test_valid_graph_lr(self):
        is_valid, _ = DiagramGenerator.validate_mermaid_code("graph LR\nA-->B")
        assert is_valid is True

    def test_mismatched_brackets(self):
        is_valid, msg = DiagramGenerator.validate_mermaid_code("flowchart TD\nA[[[[[B")
        assert is_valid is False
        assert "不一致" in msg


class TestMermaidRepair:
    """Mermaid コード修復のテスト"""

    def test_add_missing_header(self):
        result = DiagramGenerator.repair_mermaid_code("A[開始] --> B[終了]")
        assert result.startswith("flowchart TD")

    def test_empty_input(self):
        result = DiagramGenerator.repair_mermaid_code("")
        assert result == ""

    def test_replaces_double_quotes(self):
        result = DiagramGenerator.repair_mermaid_code('flowchart TD\nA["label"] --> B')
        assert '"' not in result
        assert "'" in result


class TestSimpleFlowchart:
    """シンプルフローチャート生成のテスト"""

    def test_build_from_sections(self):
        gen = DiagramGenerator.__new__(DiagramGenerator)
        sections = [
            {"title": "準備", "content": "材料を用意"},
            {"title": "実行", "content": "手順を実行"},
            {"title": "確認", "content": "結果を確認"},
        ]
        code = gen._build_simple_flowchart(sections, [])
        assert "flowchart TD" in code
        assert "準備" in code
        assert "-->" in code


class TestFallbackImage:
    """フォールバック画像生成のテスト"""

    def test_create_fallback(self, tmp_path):
        gen = DiagramGenerator.__new__(DiagramGenerator)
        output = tmp_path / "test_fallback.png"
        result = gen._create_fallback_image(
            ["ステップ1", "ステップ2", "ステップ3"],
            output
        )
        assert result.exists()
        assert result.stat().st_size > 0


class TestSaveAsMarkdown:
    """Markdown 保存のテスト"""

    def test_save_as_markdown(self, tmp_path):
        gen = DiagramGenerator.__new__(DiagramGenerator)
        output = tmp_path / "test.md"
        result = gen.save_as_markdown("flowchart TD\nA-->B", output, "Test")
        assert result.exists()
        content = result.read_text(encoding="utf-8")
        assert "# Test" in content
        assert "```mermaid" in content
        assert "flowchart TD" in content

    def test_save_as_markdown_default_title(self, tmp_path):
        gen = DiagramGenerator.__new__(DiagramGenerator)
        output = tmp_path / "test.md"
        result = gen.save_as_markdown("A[開始]", output)
        assert result.exists()
        assert "# フローチャート" in result.read_text(encoding="utf-8")


class TestSaveAsMermaid:
    """Mermaid 保存のテスト"""

    def test_save_as_mermaid(self, tmp_path):
        gen = DiagramGenerator.__new__(DiagramGenerator)
        output = tmp_path / "test.mmd"
        result = gen.save_as_mermaid("flowchart TD\nA-->B", output)
        assert result.exists()
        assert result.read_text(encoding="utf-8") == "flowchart TD\nA-->B"


class TestGenerateOptionalOutputs:
    """generate() のオプション出力テスト"""

    def test_generate_without_png(self, tmp_path):
        gen = DiagramGenerator.__new__(DiagramGenerator)
        gen.generate_mermaid_code = lambda *a, **k: "flowchart TD\nA-->B"
        gen.validate_mermaid_code = lambda code: (True, "")
        result = gen.generate(
            "text",
            [],
            [],
            output_path=None,
            markdown_path=tmp_path / "out.md",
            mermaid_path=tmp_path / "out.mmd"
        )
        assert result.image_path is None
        assert result.markdown_path is not None
        assert result.mermaid_path is not None
        assert (tmp_path / "out.md").exists()
        assert (tmp_path / "out.mmd").exists()

    def test_generate_with_png_and_md(self, tmp_path):
        gen = DiagramGenerator.__new__(DiagramGenerator)
        gen.generate_mermaid_code = lambda *a, **k: "flowchart TD\nA-->B"
        gen.validate_mermaid_code = lambda code: (True, "")
        gen.render_to_image = lambda *a, **k: tmp_path / "out.png"
        result = gen.generate(
            "text",
            [],
            [],
            output_path=tmp_path / "out.png",
            markdown_path=tmp_path / "out.md",
            mermaid_path=tmp_path / "out.mmd"
        )
        assert result.image_path is not None
        assert result.markdown_path is not None
        assert result.mermaid_path is not None


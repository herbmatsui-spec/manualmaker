"""diagram_generator.py のユニットテスト"""
import pytest
from pathlib import Path
from src.diagram_generator import DiagramGenerator, DiagramResult


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


class TestMermaidRepair:
    """Mermaid コード修復のテスト"""

    def test_add_missing_header(self):
        result = DiagramGenerator.repair_mermaid_code("A[開始] --> B[終了]")
        assert result.startswith("flowchart TD")

    def test_empty_input(self):
        result = DiagramGenerator.repair_mermaid_code("")
        assert result == ""


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

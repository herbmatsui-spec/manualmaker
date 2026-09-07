"""
Tests for Diagram Handler Module
"""

import pytest
from src.prompt_engine.handlers.diagram_handler import DiagramHandler


class TestDiagramHandler:
    """Tests for DiagramHandler class"""

    def test_initialization(self):
        handler = DiagramHandler()
        assert handler.enabled == True
        assert handler.has_diagrams == False

    def test_detect_diagram_elements_empty(self):
        handler = DiagramHandler()
        text = "これは通常のテキストです"
        elements = handler.detect_diagram_elements(text)
        assert elements["arrows"] == []
        assert elements["boxes"] == []
        assert elements["steps"] == []

    def test_detect_diagram_elements_with_arrows(self):
        handler = DiagramHandler()
        text = "開始 → 処理"
        elements = handler.detect_diagram_elements(text)
        assert len(elements["arrows"]) > 0
        assert len(elements["relationships"]) > 0

    def test_detect_diagram_elements_with_boxes(self):
        handler = DiagramHandler()
        text = "■処理1\n□処理2"
        elements = handler.detect_diagram_elements(text)
        assert len(elements["boxes"]) == 2

    def test_detect_diagram_elements_with_steps(self):
        handler = DiagramHandler()
        text = "1. 最初のステップ\n2. 次のステップ\n3. 最後のステップ"
        elements = handler.detect_diagram_elements(text)
        assert len(elements["steps"]) == 3

    def test_structure_as_markdown_normal(self):
        handler = DiagramHandler()
        text = "これは通常のテキストです"
        result = handler.structure_as_markdown(text)
        assert result == text

    def test_structure_as_markdown_with_flow(self):
        handler = DiagramHandler()
        text = "1. 開始 → 処理 → 完了"
        result = handler.structure_as_markdown(text)
        assert "流程步骤" in result or "→" in result

    def test_is_arrow_line(self):
        handler = DiagramHandler()
        assert handler.is_arrow_line("開始 → 処理") == True
        assert handler.is_arrow_line("開始 -> 処理") == True
        assert handler.is_arrow_line("開始 ⇒ 処理") == True
        assert handler.is_arrow_line("ただのテキスト") == False

    def test_extract_flow_sequence(self):
        handler = DiagramHandler()
        text = "開始 → 処理 → 完了"
        flow = handler.extract_flow_sequence(text)
        assert "開始" in flow
        assert "処理" in flow
        assert "完了" in flow

    def test_extract_flow_sequence_empty(self):
        handler = DiagramHandler()
        text = ""
        flow = handler.extract_flow_sequence(text)
        assert flow == []

    def test_validate_markdown_structure_valid(self):
        handler = DiagramHandler()
        text = """# タイトル
- 項目1
- 項目2
## サブタイトル
- 項目3"""
        issues = handler.validate_markdown_structure(text)
        assert len(issues) == 0

    def test_validate_markdown_structure_empty(self):
        handler = DiagramHandler()
        text = ""
        issues = handler.validate_markdown_structure(text)
        assert len(issues) == 0

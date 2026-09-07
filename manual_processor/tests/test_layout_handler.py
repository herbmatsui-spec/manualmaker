"""
Tests for Layout Handler Module
"""

import pytest
from src.prompt_engine.handlers.layout_handler import LayoutHandler, TextDirection


class TestLayoutHandler:
    """Tests for LayoutHandler class"""

    def test_initialization(self):
        handler = LayoutHandler()
        assert handler.direction == TextDirection.UNKNOWN
        assert handler.column_count == 1
        assert handler.has_mixed_scripts == False

    def test_detect_layout_horizontal(self):
        handler = LayoutHandler()
        text = "これはテストです。売上総利益の計算方法を示します。"
        result = handler.detect_layout(text)
        assert result in (TextDirection.HORIZONTAL, TextDirection.VERTICAL, TextDirection.MIXED)

    def test_detect_layout_empty(self):
        handler = LayoutHandler()
        result = handler.detect_layout("")
        assert result == TextDirection.UNKNOWN

    def test_detect_layout_unicode_chars(self):
        handler = LayoutHandler()
        text = "ABC DEF GHI"
        result = handler.detect_layout(text)
        assert result == TextDirection.UNKNOWN

    def test_get_reading_order_vertical(self):
        handler = LayoutHandler()
        handler.direction = TextDirection.VERTICAL
        order = handler.get_reading_order()
        assert "右の行から左" in order

    def test_get_reading_order_horizontal(self):
        handler = LayoutHandler()
        handler.direction = TextDirection.HORIZONTAL
        order = handler.get_reading_order()
        assert "左から右" in order

    def test_get_reading_order_mixed(self):
        handler = LayoutHandler()
        handler.direction = TextDirection.MIXED
        order = handler.get_reading_order()
        assert "縦書き部分" in order
        assert "横書き部分" in order

    def test_get_reading_order_unknown(self):
        handler = LayoutHandler()
        handler.direction = TextDirection.UNKNOWN
        order = handler.get_reading_order()
        assert "デフォルト" in order

    def test_reorder_lines_for_vertical(self):
        handler = LayoutHandler()
        handler.direction = TextDirection.VERTICAL
        lines = ["第1行目", "第2行目", "第3行目"]
        result = handler.reorder_lines_for_vertical(lines)
        assert result == lines

    def test_reorder_lines_non_vertical(self):
        handler = LayoutHandler()
        handler.direction = TextDirection.HORIZONTAL
        lines = ["第1行目", "第2行目", "第3行目"]
        result = handler.reorder_lines_for_vertical(lines)
        assert result == lines

    def test_detect_columns_single(self):
        handler = LayoutHandler()
        text = "単一の列のみ"
        count = handler.detect_columns(text)
        assert count >= 1

    def test_detect_columns_empty(self):
        handler = LayoutHandler()
        count = handler.detect_columns("")
        assert count == 1

    def test_merge_columns_single(self):
        handler = LayoutHandler()
        text = "単一の列のみ"
        result = handler.merge_columns_to_blocks(text, 1)
        assert result == text

    def test_merge_columns_two(self):
        handler = LayoutHandler()
        text = "第1列目\n第2列目\n第3列目\n第4列目"
        result = handler.merge_columns_to_blocks(text, 2)
        assert len(result) > 0

    def test_detect_columns_with_markers(self):
        handler = LayoutHandler()
        text = "A、B、C、D、E、F、G、H"
        count = handler.detect_columns(text)
        assert count >= 1

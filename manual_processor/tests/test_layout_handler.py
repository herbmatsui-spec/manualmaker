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


class TestLayoutHandlerFullCoverage:
    """Tests for uncovered branches in LayoutHandler"""

    def test_detect_layout_vertical_dominant(self):
        """短い漢字行のみ → 縦書き指標が優先され VERTICAL 判定"""
        handler = LayoutHandler()
        # 各行が3文字未満の漢字行 → vertical_indicators のみ増加
        text = "漢字\n漢字\n漢字"
        result = handler.detect_layout(text)
        assert result == TextDirection.VERTICAL
        assert handler.direction == TextDirection.VERTICAL

    def test_detect_layout_horizontal_dominant(self):
        """3文字以上の漢字行のみ → HORIZONTAL 判定"""
        handler = LayoutHandler()
        text = "これはテストです\n売上の計算\n利益の確認"
        result = handler.detect_layout(text)
        assert result == TextDirection.HORIZONTAL

    def test_detect_layout_mixed(self):
        """横書き指標と縦書き指標の差が1以下 → MIXED 判定"""
        handler = LayoutHandler()
        # 横書き指標1 + 縦書き指標1 → 差0 → MIXED
        text = "これはテスト行です\n漢字"
        result = handler.detect_layout(text)
        assert result == TextDirection.MIXED
        assert handler.has_mixed_scripts is True

    def test_detect_layout_japanese_kana_only(self):
        """ひらがな・カタカナのみでも Japanese 文字としてカウントされる"""
        handler = LayoutHandler()
        text = "ひらがなカタカナ"
        result = handler.detect_layout(text)
        assert result in (TextDirection.HORIZONTAL, TextDirection.VERTICAL, TextDirection.MIXED)

    def test_reorder_lines_with_empty_lines(self):
        """空白行を含む行の並び替え（空白行ブランチをカバー）"""
        handler = LayoutHandler()
        handler.direction = TextDirection.VERTICAL
        lines = ["第1行目", "", "  ", "第3行目"]
        result = handler.reorder_lines_for_vertical(lines)
        assert result == lines

    def test_detect_columns_two_by_marker_count(self):
        """区切り文字が3超 → 2列判定"""
        handler = LayoutHandler()
        text = "項目A、項目B、項目C、項目D\n項目E、項目F、項目G、項目H"
        count = handler.detect_columns(text)
        assert count == 2

    def test_detect_columns_two_by_line_length(self):
        """行長が類似し平均長が30超 → 2列判定"""
        handler = LayoutHandler()
        # 各行40文字で区切り文字なし
        line1 = "あ" * 40
        line2 = "い" * 40
        text = f"{line1}\n{line2}"
        count = handler.detect_columns(text)
        assert count == 2

    def test_detect_columns_single_line_returns_1(self):
        """1行のみ → 1列"""
        handler = LayoutHandler()
        assert handler.detect_columns("一行だけのテキストです") == 1

    def test_detect_columns_whitespace_only_returns_1(self):
        """空白行のみ → 1列"""
        handler = LayoutHandler()
        assert handler.detect_columns("  \n \n  ") == 1

    def test_detect_columns_different_length_returns_1(self):
        """行長の差が5以上 → 1列"""
        handler = LayoutHandler()
        line1 = "あ" * 10
        line2 = "い" * 40
        text = f"{line1}\n{line2}"
        assert handler.detect_columns(text) == 1

    def test_merge_columns_too_few_lines_returns_text(self):
        """行数が num_columns*2 未満 → 元テキストをそのまま返す"""
        handler = LayoutHandler()
        text = "第1行\n第2行\n第3行"
        result = handler.merge_columns_to_blocks(text, 2)
        assert result == text

    def test_merge_columns_too_few_non_empty_returns_text(self):
        """非空行数が num_columns*2 未満 → 元テキストをそのまま返す"""
        handler = LayoutHandler()
        # 非空行3 < num_columns*2=4 → 早期リターン
        text = "第1行\n\n第2行\n\n第3行"
        result = handler.merge_columns_to_blocks(text, 2)
        assert result == text

    def test_merge_columns_success(self):
        """正常な列マージ（2列 × 2行）"""
        handler = LayoutHandler()
        text = "A1\nA2\nB1\nB2"
        result = handler.merge_columns_to_blocks(text, 2)
        assert result == "A1\nA2\n\nB1\nB2"

    def test_merge_columns_uneven_block_size(self):
        """端数のある列マージ（最後の列が残りをすべて受け取る）"""
        handler = LayoutHandler()
        # 8非空行, block_size = 8//3 = 2 → [A1,A2] [A3,B1] [B2,B3,B4,B5]
        text = "A1\nA2\nA3\nB1\nB2\nB3\nB4\nB5"
        result = handler.merge_columns_to_blocks(text, 3)
        blocks = result.split("\n\n")
        assert len(blocks) == 3
        assert blocks[0] == "A1\nA2"
        assert blocks[1] == "A3\nB1"
        assert blocks[2] == "B2\nB3\nB4\nB5"

    def test_get_reading_order_explicit_direction(self):
        """明示的な direction 引数を渡した場合"""
        handler = LayoutHandler()
        order = handler.get_reading_order(TextDirection.VERTICAL)
        assert "右の行から左" in order

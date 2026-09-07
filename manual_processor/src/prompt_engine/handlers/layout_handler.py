"""
Layout Handler Module
Handles layout detection and reading order for vertical/horizontal Japanese text
"""

import logging
from enum import Enum
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)


class TextDirection(Enum):
    """Text direction enumeration"""
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class LayoutHandler:
    """Handler for detecting and processing Japanese text layouts"""

    def __init__(self):
        self.direction = TextDirection.UNKNOWN
        self.column_count = 1
        self.has_mixed_scripts = False

    def detect_layout(self, text: str) -> TextDirection:
        """
        Detect text layout direction

        Args:
            text: OCR output text

        Returns:
            Detected text direction
        """
        if not text:
            self.direction = TextDirection.UNKNOWN
            return self.direction

        japanese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        hiragana = sum(1 for c in text if '\u3040' <= c <= '\u309f')
        katakana = sum(1 for c in text if '\u30a0' <= c <= '\u30ff')
        total_japanese = japanese_chars + hiragana + katakana

        if total_japanese == 0:
            self.direction = TextDirection.UNKNOWN
            return self.direction

        horizontal_indicators = 0
        vertical_indicators = 0

        lines = text.split('\n')
        for line in lines:
            if len(line) > 0:
                if any('\u4e00' <= c <= '\u9fff' for c in line):
                    if len(line) >= 3:
                        horizontal_indicators += 1
                    else:
                        vertical_indicators += 1

        if abs(horizontal_indicators - vertical_indicators) < 2:
            self.direction = TextDirection.MIXED
            self.has_mixed_scripts = True
        elif horizontal_indicators > vertical_indicators:
            self.direction = TextDirection.HORIZONTAL
        else:
            self.direction = TextDirection.VERTICAL

        logger.info(f"Layout detected: {self.direction.value}")
        return self.direction

    def get_reading_order(self, direction: TextDirection = None) -> str:
        """
        Get reading order instruction based on direction

        Args:
            direction: Text direction (uses self.direction if None)

        Returns:
            Reading order instruction string
        """
        if direction is None:
            direction = self.direction

        if direction == TextDirection.VERTICAL:
            return "右の行から左の行へ向かって順番に読み取ってください。"
        elif direction == TextDirection.HORIZONTAL:
            return "左から右、上から下へ向かって順番に読み取ってください。"
        elif direction == TextDirection.MIXED:
            return """以下の複合レイアウトの読み取り規則を守ってください：
- 縦書き部分：右の行から左の行へ向かって読み取る
- 横書き部分：左から右、上から下へ向かって読み取る
- 図表や矢印は文脈に従って順番に読み取る"""
        else:
            return "左から右、上から下へ向かって順番に読み取ってください。（デフォルト）"

    def reorder_lines_for_vertical(self, lines: List[str]) -> List[str]:
        """
        Reorder lines for vertical text reading (right to left columns)

        Args:
            lines: List of text lines

        Returns:
            Reordered lines
        """
        if self.direction != TextDirection.VERTICAL:
            return lines

        reordered = []
        i = 0
        while i < len(lines):
            if len(lines[i].strip()) == 0:
                reordered.append(lines[i])
            else:
                reordered.append(lines[i])
            i += 1

        return reordered

    def detect_columns(self, text: str) -> int:
        """
        Detect number of text columns in the document

        Args:
            text: OCR output text

        Returns:
            Estimated column count
        """
        if not text:
            return 1

        lines = text.split('\n')
        if len(lines) < 2:
            return 1

        non_empty_lines = [l for l in lines if l.strip()]
        if len(non_empty_lines) < 2:
            return 1

        first_line_len = len(non_empty_lines[0])
        second_line_len = len(non_empty_lines[1])

        avg_len = sum(len(l) for l in non_empty_lines) / len(non_empty_lines)

        column_markers = [',', '、', ';', '；', ':', '：']
        marker_counts = [text.count(m) for m in column_markers]
        max_markers = max(marker_counts) if marker_counts else 0

        if max_markers > 3:
            return 2

        if abs(first_line_len - second_line_len) < 5 and avg_len > 30:
            return 2

        return 1

    def merge_columns_to_blocks(self, text: str, num_columns: int = 2) -> str:
        """
        Merge multiple columns into coherent blocks

        Args:
            text: OCR output text
            num_columns: Number of columns detected

        Returns:
            Merged text
        """
        if num_columns < 2:
            return text

        lines = text.split('\n')
        if len(lines) < num_columns * 2:
            return text

        non_empty = [i for i, l in enumerate(lines) if l.strip()]
        if len(non_empty) < num_columns * 2:
            return text

        block_size = len(non_empty) // num_columns
        blocks = []

        for col in range(num_columns):
            start_idx = col * block_size
            end_idx = start_idx + block_size if col < num_columns - 1 else len(non_empty)
            col_lines = [lines[non_empty[i]] for i in range(start_idx, end_idx)]
            blocks.append('\n'.join(col_lines))

        return '\n\n'.join(blocks)

"""
Diagram Handler Module
Handles diagram and flowchart structure extraction from OCR text
"""

import re
import logging
from typing import List, Tuple, Dict, Optional

logger = logging.getLogger(__name__)

ARROW_PATTERNS: List[str] = [
    r'→', r'→', r'⇒', r'->', r'=>', r'→', r'⟶', r'➔',
    r'↑', r'↓', r'←', r'→', r'↗', r'↘', r'↙', r'↖',
]

MARKDOWN_ARROW: str = " → "


class DiagramHandler:
    """Handler for processing diagrams, flowcharts, and visual elements from OCR"""

    def __init__(self):
        self.enabled = True
        self.has_diagrams = False

    def detect_diagram_elements(self, text: str) -> Dict[str, List[str]]:
        """
        Detect diagram elements in OCR text

        Args:
            text: OCR output text

        Returns:
            Dictionary with detected elements
        """
        elements = {
            "arrows": [],
            "boxes": [],
            "steps": [],
            "relationships": []
        }

        lines = text.split('\n')
        for line in lines:
            for pattern in ARROW_PATTERNS:
                if pattern in line:
                    elements["arrows"].append(line)
                    parts = line.split(pattern)
                    if len(parts) == 2:
                        elements["relationships"].append({
                            "from": parts[0].strip(),
                            "to": parts[1].strip(),
                            "connector": pattern
                        })
                    break

            if re.match(r'^\s*[\u25a0\u25b6\u25cf\u25a1\u25c6\u25c7]\s*', line):
                elements["boxes"].append(line.strip())

            step_match = re.match(r'^\s*(\d+|[①②③④⑤⑥⑦⑧⑨⑩]|[一二三四五六七八九十]+)[\.、.)\]]\s*(.+)', line)
            if step_match:
                elements["steps"].append({
                    "number": step_match.group(1),
                    "content": step_match.group(2)
                })

        self.has_diagrams = any(elements.values())
        return elements

    def structure_as_markdown(self, text: str) -> str:
        """
        Convert diagram-like text to structured markdown

        Args:
            text: OCR output text

        Returns:
            Markdown formatted text
        """
        elements = self.detect_diagram_elements(text)

        if not any(elements.values()):
            return text

        result_parts = []

        if elements["steps"]:
            result_parts.append("## 流程步骤\n")
            for step in elements["steps"]:
                result_parts.append(f"{step['number']}. {step['content']}")
            result_parts.append("")

        if elements["relationships"]:
            result_parts.append("## 関連図\n")
            for rel in elements["relationships"]:
                result_parts.append(f"- {rel['from']} {MARKDOWN_ARROW} {rel['to']}")
            result_parts.append("")

        if elements["boxes"]:
            result_parts.append("## 要素一覧\n")
            for box in elements["boxes"]:
                result_parts.append(f"- {box}")
            result_parts.append("")

        return '\n'.join(result_parts) if result_parts else text

    def is_arrow_line(self, line: str) -> bool:
        """
        Check if a line contains an arrow connector

        Args:
            line: Text line to check

        Returns:
            True if line contains an arrow
        """
        for pattern in ARROW_PATTERNS:
            if pattern in line:
                return True
        return False

    def extract_flow_sequence(self, text: str) -> List[str]:
        """
        Extract sequential flow from arrow-connected text

        Args:
            text: OCR output text

        Returns:
            List of flow items in order
        """
        lines = text.split('\n')
        flow = []

        for line in lines:
            if self.is_arrow_line(line):
                parts = line
                for pattern in ARROW_PATTERNS:
                    parts = parts.replace(pattern, '|||')
                items = [p.strip() for p in parts.split('|||') if p.strip()]
                flow.extend(items)
            elif line.strip() and not self.is_arrow_line(line):
                flow.append(line.strip())

        return flow

    def validate_markdown_structure(self, text: str) -> List[str]:
        """
        Validate that markdown structure is well-formed

        Args:
            text: Markdown text to validate

        Returns:
            List of validation issues
        """
        issues = []
        lines = text.split('\n')

        in_list = False
        list_indent = 0

        for line_num, line in enumerate(lines, 1):
            if re.match(r'^\s*[-*+]\s+', line):
                if not in_list:
                    in_list = True
                    list_indent = len(line) - len(line.lstrip())
                elif len(line) - len(line.lstrip()) != list_indent:
                    issues.append(f"Line {line_num}: Inconsistent list indentation")

            elif re.match(r'^#{1,6}\s+', line):
                in_list = False

            elif line.strip() and in_list and not re.match(r'^\s', line):
                if line.strip() and not re.match(r'^[#\-+*]', line.strip()[0]):
                    in_list = False

        return issues

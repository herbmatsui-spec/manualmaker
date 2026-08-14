"""
Result Formatter Module
Converts GeminiResult and other model outputs into formatted Markdown text for generators.
"""

import logging
from typing import Any, Union
from src.gemini_processor import GeminiResult

logger = logging.getLogger(__name__)


def format_to_markdown(result: Union[GeminiResult, dict, str, Any]) -> str:
    """
    Converts a GeminiResult object, dictionary, or string into a well-structured Markdown string.

    Args:
        result: GeminiResult, dict, or str

    Returns:
        Formatted Markdown text suitable for PDF/DOCX generators.
    """
    if isinstance(result, str):
        return result

    if isinstance(result, dict):
        # Dictionary format fallback
        title = result.get('title', 'マニュアル')
        summary = result.get('summary', '')
        key_points = result.get('key_points', [])
        sections = result.get('sections', [])
        glossary = result.get('glossary', [])
    elif isinstance(result, GeminiResult):
        title = result.title or "マニュアル"
        summary = result.summary or ""
        key_points = result.key_points or []
        sections = result.sections or []
        glossary = result.glossary or []
    else:
        return str(result)

    markdown_lines = []

    # Title
    if title:
        markdown_lines.append(f"# {title}\n")

    # Summary
    if summary:
        markdown_lines.append("## 概要")
        markdown_lines.append(summary.strip())
        markdown_lines.append("")

    # Key Points
    if key_points:
        markdown_lines.append("## 重要ポイント")
        for point in key_points:
            markdown_lines.append(f"- {point.strip()}")
        markdown_lines.append("")

    # Sections
    if sections:
        for section in sections:
            sec_title = getattr(section, 'title', None) or (section.get('title') if isinstance(section, dict) else "")
            sec_content = getattr(section, 'content', None) or (section.get('content') if isinstance(section, dict) else "")
            
            if sec_title:
                markdown_lines.append(f"## {sec_title}")
            if sec_content:
                markdown_lines.append(sec_content.strip())
            markdown_lines.append("")

    # Glossary
    if glossary:
        markdown_lines.append("## 用語集")
        for item in glossary:
            if isinstance(item, dict):
                term = item.get('term', '')
                explanation = item.get('explanation', '')
                if term and explanation:
                    markdown_lines.append(f"- **{term}**: {explanation}")
                elif term:
                    markdown_lines.append(f"- {term}")
            elif isinstance(item, str):
                markdown_lines.append(f"- {item}")
        markdown_lines.append("")

    return "\n".join(markdown_lines).strip()

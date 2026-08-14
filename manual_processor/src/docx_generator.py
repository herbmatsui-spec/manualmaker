"""
Word Document Generator Module
Creates formatted Word documents from processed text
"""

import logging
from pathlib import Path
from typing import Optional

try:
    from docx import Document
    from docx.shared import Pt, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
except ImportError:
    Document = None

logger = logging.getLogger(__name__)


class WordGenerator:
    """Generates formatted Word documents"""
    
    def __init__(self):
        """Initialize Word generator"""
        if Document is None:
            raise ImportError("python-docx is required for Word generation. Install with: pip install python-docx")
        logger.debug("WordGenerator initialized")
    
    def insert_diagram_image(self, document: Document, image_path: Path,
                             caption: str = "作業フロー図") -> None:
        """Word文書にフローチャート画像を挿入"""
        if not image_path or not Path(image_path).exists():
            return

        try:
            document.add_heading(f"📊 {caption}", level=1)
            document.add_picture(str(image_path), width=Inches(6.0))
            caption_para = document.add_paragraph("※ 上記フローチャートはAIが自動生成したものです。")
            caption_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            logger.info(f"Inserted diagram image into Word document: {image_path}")
        except Exception as e:
            logger.warning(f"Word への画像挿入失敗: {e}")

    def generate_word(self, content: str, output_path: Path, title: str = "Processed Manual",
                      compact_layout: bool = False, use_emojis: bool = False,
                      diagram_path: Optional[Path] = None) -> Path:
        """
        Generate a formatted Word document
        """
        document = Document()
        
        # Title
        display_title = f"📄 {title}" if use_emojis else title
        heading = document.add_heading(display_title, 0)
        heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if compact_layout:
            for run in heading.runs:
                run.font.size = Pt(22)
        
        base_font_size = Pt((13 if compact_layout else 11))
        for line in content.split('\n'):
            if line.strip().startswith('## '):
                # Section header
                header_text = line[3:].strip()
                if use_emojis:
                    header_text = f"📌 {header_text}"
                heading = document.add_heading(header_text, level=(1 if not compact_layout else 1))
                if compact_layout:
                    for run in heading.runs:
                        run.font.size = Pt(16)
                        if compact_layout:
                            heading.paragraph_format.space_after = Pt(2)
                            heading.paragraph_format.space_before = Pt(2)
            elif line.strip().startswith('### '):
                # Sub-section header
                header_text = line[4:].strip()
                if use_emojis:
                    header_text = f"📌 {header_text}"
                heading = document.add_heading(header_text, level=2)
                if compact_layout:
                    for run in heading.runs:
                        run.font.size = Pt(14)
                        heading.paragraph_format.space_after = Pt(2)
                        heading.paragraph_format.space_before = Pt(2)
            elif line.strip().startswith('- ') or line.strip().startswith('• '):
                # Bullet point
                bullet_text = line.strip()[2:]
                if use_emojis:
                    bullet_text = f"🔹 {bullet_text}"
                bullet_point = document.add_paragraph(style='List Bullet')
                run = bullet_point.add_run(bullet_text)
                run.font.size = base_font_size
                if compact_layout:
                    bullet_point.paragraph_format.space_after = Pt(2)
                    bullet_point.paragraph_format.line_spacing = 1.0
            elif line.strip():
                # Regular paragraph
                paragraph = document.add_paragraph(line.strip())
                if compact_layout:
                    for run in paragraph.runs:
                        run.font.size = base_font_size
                    paragraph.paragraph_format.space_after = Pt((1 if compact_layout else 6))
                    paragraph.paragraph_format.line_spacing = 1.0
        
        # Insert diagram image if present
        if diagram_path and Path(diagram_path).exists():
            self.insert_diagram_image(document, Path(diagram_path))

        # Save document
        output_path.parent.mkdir(parents=True, exist_ok=True)
        document.save(str(output_path))
        logger.info(f"Word document generated: {output_path}")
        
        return output_path


def create_word_document(content: str, output_path: Path, title: str = "Processed Manual",
                         compact_layout: bool = False, use_emojis: bool = False,
                         diagram_path: Optional[Path] = None) -> Path:
    """
    Convenience function to generate Word document
    """
    generator = WordGenerator()
    return generator.generate_word(content, output_path, title, compact_layout=compact_layout,
                                  use_emojis=use_emojis, diagram_path=diagram_path)
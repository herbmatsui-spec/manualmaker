"""
PDF Generator Module
Creates formatted PDF documents from processed text
"""

import logging
from pathlib import Path
from typing import Optional

try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

from src.utils.path_resolver import get_resource_path

logger = logging.getLogger(__name__)


class PDFGenerator:
    """Generates formatted PDF documents"""
    
    def __init__(self):
        """Initialize PDF generator"""
        if FPDF is None:
            raise ImportError("fpdf2 is required for PDF generation. Install with: pip install fpdf2")
        logger.debug("PDFGenerator initialized")
    
    def insert_diagram_image(self, pdf: FPDF, image_path: Path,
                             caption: str = "作業フロー図",
                             font_name: str = "JPFont") -> None:
        """PDF にフローチャート画像を挿入"""
        if not image_path or not Path(image_path).exists():
            return

        try:
            pdf.add_page()
            pdf.set_font(font_name, "B", 14)
            pdf.cell(0, 10, f"📊 {caption}", ln=True, align="C")
            pdf.ln(5)

            page_width = pdf.w - pdf.l_margin - pdf.r_margin
            pdf.image(str(image_path), x=pdf.l_margin, w=page_width)
            logger.info(f"Inserted diagram image into PDF: {image_path}")
        except Exception as e:
            logger.warning(f"PDF への画像挿入失敗: {e}")

    def generate_pdf(self, content: str, output_path: Path, title: str = "Processed Manual",
                     compact_layout: bool = False, use_emojis: bool = False,
                     diagram_path: Optional[Path] = None) -> Path:
        """
        Generate a formatted PDF document
        """
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=(8 if compact_layout else 15))
        
        # 1. Bundled fonts via path_resolver
        import os
        jp_font_path = None
        
        # Check bundled assets first
        bundled_candidates = [
            get_resource_path("assets/fonts/font.ttf"),
            get_resource_path("assets/fonts/IPAexGothic.ttf"),
            get_resource_path("assets/fonts/NotoSansJP.ttf"),
            get_resource_path("assets/fonts/msgothic.ttc")
        ]
        
        for candidate in bundled_candidates:
            if candidate and candidate.exists():
                jp_font_path = str(candidate)
                break
                
        # Fallback to system fonts if no bundled font found
        if not jp_font_path:
            system_candidates = [
                "C:/Windows/Fonts/msgothic.ttc",
                "C:/Windows/Fonts/msmincho.ttc",
                "C:/Windows/Fonts/meiryo.ttc",
                "C:/Windows/Fonts/yugothm.ttc",
                "DejaVuSans.ttf"
            ]
            for candidate in system_candidates:
                if os.path.exists(candidate):
                    jp_font_path = candidate
                    break
        
        font_name = "JPFont" if jp_font_path else "Helvetica"
        if jp_font_path:
            try:
                pdf.add_font(font_name, "", jp_font_path)
                pdf.add_font(font_name, "B", jp_font_path)
            except Exception as e:
                logger.warning(f"Font loading warning: {e}")
                font_name = "Helvetica"
        else:
            pdf.set_font("Helvetica", size=(13 if compact_layout else 12))
            
        pdf.set_font(font_name, size=(13 if compact_layout else 12))
        
        # Title page
        pdf.add_page()
        display_title = f"📄 {title}" if use_emojis else title
        pdf.set_font(font_name, "B" if jp_font_path else "", (22 if compact_layout else 20))
        pdf.cell(0, (10 if compact_layout else 15), display_title, ln=True, align="C")
        pdf.ln((6 if compact_layout else 10))
        
        # Content
        pdf.set_font(font_name, size=(12 if compact_layout else 11))
        body_line_height = (6 if compact_layout else 8)
        header_line_height = (8 if compact_layout else 10)
        header_space_after = (2 if compact_layout else 4)
        bullet_space_after = (1 if compact_layout else 2)
        regular_space_after = (1 if compact_layout else 2)
        for line in content.split('\n'):
            if line.strip().startswith('## '):
                # Section header
                header_text = line[3:].strip()
                if use_emojis:
                    header_text = f"📌 {header_text}"
                pdf.set_font(font_name, "B" if jp_font_path else "", (16 if compact_layout else 14))
                pdf.cell(0, header_line_height, header_text, ln=True)
                pdf.set_font(font_name, size=(12 if compact_layout else 11))
                pdf.ln(header_space_after)
            elif line.strip().startswith('- ') or line.strip().startswith('• '):
                # Bullet point
                bullet_text = line.strip()[2:]
                if use_emojis:
                    bullet_text = f"🔹 {bullet_text}"
                pdf.cell(10)
                pdf.multi_cell(0, body_line_height, bullet_text)
                pdf.ln(bullet_space_after)
            else:
                # Regular text
                pdf.multi_cell(0, body_line_height, line.strip())
                pdf.ln(regular_space_after)
        
        # Insert diagram image if present
        if diagram_path and Path(diagram_path).exists():
            self.insert_diagram_image(pdf, Path(diagram_path), font_name=font_name)

        # Save PDF
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pdf.output(str(output_path))
        logger.info(f"PDF generated: {output_path}")
        
        return output_path


def create_formatted_pdf(content: str, output_path: Path, title: str = "Processed Manual",
                         compact_layout: bool = False, use_emojis: bool = False,
                         diagram_path: Optional[Path] = None) -> Path:
    """
    Convenience function to generate PDF
    """
    generator = PDFGenerator()
    return generator.generate_pdf(content, output_path, title, compact_layout=compact_layout,
                                  use_emojis=use_emojis, diagram_path=diagram_path)
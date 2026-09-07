"""
PDF Generator Module
Creates formatted PDF documents from processed text
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

from src.utils.path_resolver import get_resource_path

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "pdf"


class TemplateLoadError(Exception):
    """Template loading error"""
    pass


class TemplateLoader:
    """Loads and manages PDF output templates"""

    _cache: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def load_template(cls, name: str) -> Dict[str, Any]:
        """
        Load a template by name.

        Args:
            name: Template name (e.g., "default", "compact")

        Returns:
            Template dictionary

        Raises:
            TemplateLoadError: If template cannot be loaded
        """
        if name in cls._cache:
            return cls._cache[name]

        template_path = TEMPLATE_DIR / f"{name}.json"
        if not template_path.exists():
            raise TemplateLoadError(f"Template not found: {name}")

        try:
            with open(template_path, "r", encoding="utf-8") as f:
                template = json.load(f)
        except Exception as e:
            raise TemplateLoadError(f"Failed to load template {name}: {e}")

        cls._cache[name] = template
        logger.debug(f"Loaded template: {name}")
        return template

    @classmethod
    def resolve_template(cls, template: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve template inheritance (parent templates).

        Args:
            template: Template dictionary

        Returns:
            Fully resolved template with inherited values merged
        """
        if not template.get("parent"):
            return template

        parent_name = template["parent"]
        parent_template = cls.load_template(parent_name)
        resolved_parent = cls.resolve_template(parent_template)

        merged = resolved_parent.copy()
        merged.update(template)
        return merged

    @classmethod
    def validate_template(cls, template: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate a template dictionary.

        Returns:
            (is_valid, error_message)
        """
        required_fields = ["name", "layout", "sections_order"]
        for field in required_fields:
            if field not in template:
                return False, f"Missing required field: {field}"

        if not isinstance(template["sections_order"], list):
            return False, "sections_order must be a list"

        valid_layouts = ["standard", "compact", "fancy"]
        if template["layout"] not in valid_layouts:
            return False, f"Invalid layout: {template['layout']}"

        return True, ""

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the template cache"""
        cls._cache.clear()


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
                     diagram_path: Optional[Path] = None,
                     template: Optional[Dict[str, Any]] = None) -> Path:
        """
        Generate a formatted PDF document

        Args:
            content: Text content for the PDF
            output_path: Output file path
            title: Document title
            compact_layout: If True, use compact layout (for backwards compatibility)
            use_emojis: If True, insert emojis
            diagram_path: Optional path to diagram image
            template: Optional template dictionary. If provided, template settings override
                     compact_layout and use_emojis flags.
        """
        if template:
            t = template
        else:
            t = {
                "font_size": 11 if not compact_layout else 13,
                "margin": 15 if not compact_layout else 12,
                "compact_mode": compact_layout,
                "emoji_enabled": use_emojis,
                "title_font_size": 20 if not compact_layout else 22,
                "header_font_size": 14 if not compact_layout else 16,
                "body_line_height": 8 if not compact_layout else 6,
                "header_line_height": 10 if not compact_layout else 8,
                "header_space_after": 4 if not compact_layout else 2,
                "bullet_space_after": 2 if not compact_layout else 1,
                "page_break_before_diagram": True
            }

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=t.get("margin", 15))
        
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
            
        pdf.set_font(font_name, size=t.get("font_size", 12))

        # Title page
        pdf.add_page()
        use_emojis_flag = t.get("emoji_enabled", use_emojis)
        display_title = f"📄 {title}" if use_emojis_flag else title
        pdf.set_font(font_name, "B" if jp_font_path else "", t.get("title_font_size", 20))
        pdf.cell(0, (10 if t.get("compact_mode") else 15), display_title, ln=True, align="C")
        pdf.ln((6 if t.get("compact_mode") else 10))

        # Content
        pdf.set_font(font_name, size=t.get("font_size", 11))
        body_line_height = t.get("body_line_height", 8)
        header_line_height = t.get("header_line_height", 10)
        header_space_after = t.get("header_space_after", 4)
        bullet_space_after = t.get("bullet_space_after", 2)
        regular_space_after = t.get("regular_space_after", 2)
        for line in content.split('\n'):
            if line.strip().startswith('## '):
                # Section header
                header_text = line[3:].strip()
                if use_emojis_flag:
                    header_text = f"📌 {header_text}"
                pdf.set_font(font_name, "B" if jp_font_path else "", t.get("header_font_size", 14))
                pdf.cell(0, header_line_height, header_text, ln=True)
                pdf.set_font(font_name, size=t.get("font_size", 11))
                pdf.ln(header_space_after)
            elif line.strip().startswith('- ') or line.strip().startswith('• '):
                # Bullet point
                bullet_text = line.strip()[2:]
                if use_emojis_flag:
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
                         diagram_path: Optional[Path] = None,
                         template_name: str = None) -> Path:
    """
    Convenience function to generate PDF

    Args:
        content: Text content for the PDF
        output_path: Output file path
        title: Document title
        compact_layout: If True, use compact layout (for backwards compatibility)
        use_emojis: If True, insert emojis
        diagram_path: Optional path to diagram image
        template_name: Template name to use (e.g., "default", "compact").
                      If None, uses compact_layout/emoji flags for backwards compatibility.
    """
    generator = PDFGenerator()

    if template_name:
        try:
            template = TemplateLoader.load_template(template_name)
            resolved = TemplateLoader.resolve_template(template)
            is_valid, error = TemplateLoader.validate_template(resolved)
            if not is_valid:
                logger.warning(f"Template validation failed ({error}), using defaults")
                resolved = None
        except TemplateLoadError as e:
            logger.warning(f"Template loading failed: {e}, using defaults")
            resolved = None
    else:
        resolved = None

    return generator.generate_pdf(
        content, output_path, title,
        compact_layout=compact_layout,
        use_emojis=use_emojis,
        diagram_path=diagram_path,
        template=resolved
    )
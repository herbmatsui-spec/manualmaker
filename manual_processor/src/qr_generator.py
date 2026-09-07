"""
QR Code Generator Module
Generates QR code PNG images for mobile playback links and sharing
"""

import logging
from pathlib import Path
from typing import Optional

try:
    import qrcode
    from qrcode import QRCode
    from qrcode.image.styledpil import StyledPilImage
    from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False

logger = logging.getLogger(__name__)


class QRCodeError(Exception):
    """QR code generation error"""
    pass


class QRGenerator:
    """Generates QR code PNG images"""

    def __init__(self, box_size: int = 10, border: int = 2,
                 fill_color: str = "black", back_color: str = "white",
                 error_correction: str = "M"):
        """
        Initialize QR generator

        Args:
            box_size: Size of each QR module in pixels
            border: Border size in modules (min 4 recommended for readability)
            fill_color: QR code foreground color
            back_color: QR code background color
            error_correction: Error correction level (L/M/Q/H)
        """
        if not QRCODE_AVAILABLE:
            raise ImportError(
                "qrcode is required for QR code generation. "
                "Install with: pip install qrcode[pil]"
            )

        self.box_size = box_size
        self.border = border
        self.fill_color = fill_color
        self.back_color = back_color

        error_levels = {
            "L": qrcode.constants.ERROR_CORRECT_L,
            "M": qrcode.constants.ERROR_CORRECT_M,
            "Q": qrcode.constants.ERROR_CORRECT_Q,
            "H": qrcode.constants.ERROR_CORRECT_H,
        }
        if error_correction not in error_levels:
            raise QRCodeError(f"Invalid error correction level: {error_correction}")
        self.error_correction = error_levels[error_correction]

    def generate_qr(self, url: str, output_path: Path, title: str = "") -> Path:
        """
        Generate a QR code PNG image

        Args:
            url: URL to encode in the QR code
            output_path: Output file path (PNG)
            title: Optional title for logging

        Returns:
            Path to the generated PNG file
        """
        if not url:
            raise QRCodeError("URL cannot be empty")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            qr = QRCode(
                version=None,
                error_correction=self.error_correction,
                box_size=self.box_size,
                border=self.border,
            )
            qr.add_data(url)
            qr.make(fit=True)

            img = qr.make_image(
                fill_color=self.fill_color,
                back_color=self.back_color,
            )

            img.save(str(output_path))
            logger.info(f"QR code generated: {output_path} (URL: {url[:60]}...)")
            return output_path

        except Exception as e:
            raise QRCodeError(f"Failed to generate QR code: {e}")


def create_qr_code(url: str, output_path: Path, title: str = "") -> Path:
    """
    Convenience function to generate a QR code

    Args:
        url: URL to encode
        output_path: Output PNG path
        title: Optional title for logging

    Returns:
        Path to generated PNG
    """
    generator = QRGenerator()
    return generator.generate_qr(url, output_path, title=title)

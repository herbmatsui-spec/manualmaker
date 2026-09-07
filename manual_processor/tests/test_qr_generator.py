"""
Tests for QR code generator module
"""

import tempfile
from pathlib import Path

import pytest
from PIL import Image

from src.qr_generator import QRGenerator, create_qr_code, QRCodeError, QRCODE_AVAILABLE


@pytest.mark.skipif(not QRCODE_AVAILABLE, reason="qrcode package not installed")
class TestQRGenerator:
    """Test QRGenerator class"""

    def test_generate_qr_creates_png(self):
        """QRコードPNGが正常に生成される"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_qr.png"
            generator = QRGenerator()
            result = generator.generate_qr("https://example.com", output_path)

            assert result.exists()
            assert result.suffix == ".png"

    def test_generate_qr_creates_parent_directories(self):
        """出力先ディレクトリが自動作成される"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "subdir" / "nested" / "test_qr.png"
            generator = QRGenerator()
            result = generator.generate_qr("https://example.com", output_path)

            assert result.exists()
            assert output_path.parent.exists()

    def test_generate_qr_valid_png(self):
        """生成ファイルが実際にPNG形式である"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_qr.png"
            generator = QRGenerator()
            generator.generate_qr("https://example.com", output_path)

            img = Image.open(output_path)
            assert img.format == "PNG"

    def test_generate_qr_minimum_size(self):
        """QRコードが最小サイズ以上で生成される"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_qr.png"
            generator = QRGenerator(box_size=10, border=2)
            generator.generate_qr("https://example.com", output_path)

            img = Image.open(output_path)
            assert img.size[0] >= 200
            assert img.size[1] >= 200

    def test_generate_qr_custom_size(self):
        """カスタムbox_sizeで生成される"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_qr.png"
            generator = QRGenerator(box_size=5, border=1)
            generator.generate_qr("https://example.com", output_path)

            img = Image.open(output_path)
            assert img.size[0] >= 100  # smaller than default but still valid

    def test_generate_qr_empty_url_raises(self):
        """空のURLでエラーが発生する"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_qr.png"
            generator = QRGenerator()

            with pytest.raises(QRCodeError, match="URL cannot be empty"):
                generator.generate_qr("", output_path)

    def test_generate_qr_long_url(self):
        """長いURLもエンコードできる"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_qr.png"
            generator = QRGenerator()
            long_url = "https://drive.google.com/file/d/abc123xyz789/view?usp=sharing&resourcekey=abcdef"
            result = generator.generate_qr(long_url, output_path)

            assert result.exists()
            img = Image.open(result)
            assert img.format == "PNG"

    def test_generate_qr_japanese_characters(self):
        """日本語を含むURLもエンコードできる"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_qr.png"
            generator = QRGenerator()
            url_with_japanese = "https://example.com/マニュアル/123"
            result = generator.generate_qr(url_with_japanese, output_path)

            assert result.exists()
            img = Image.open(result)
            assert img.format == "PNG"

    def test_qr_image_white_background(self):
        """QRコードの背景が白である"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_qr.png"
            generator = QRGenerator(box_size=10, border=2)
            generator.generate_qr("https://example.com", output_path)

            img = Image.open(output_path)
            # Convert to RGB to check pixel colors
            img_rgb = img.convert("RGB")
            pixel = img_rgb.getpixel((0, 0))
            assert pixel[0] >= 250 and pixel[1] >= 250 and pixel[2] >= 250

    def test_convenience_function(self):
        """create_qr_code 便利関数が動作する"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_qr.png"
            result = create_qr_code("https://example.com", output_path)

            assert result.exists()
            img = Image.open(result)
            assert img.format == "PNG"

    def test_error_correction_levels(self):
        """各エラー訂正レベルでQRが生成される"""
        for level in ["L", "M", "Q", "H"]:
            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = Path(tmpdir) / f"test_qr_{level}.png"
                generator = QRGenerator(error_correction=level)
                result = generator.generate_qr("https://example.com", output_path)

                assert result.exists()
                img = Image.open(result)
                assert img.format == "PNG"

    def test_invalid_error_correction_raises(self):
        """無効なエラー訂正レベルでエラーが発生する"""
        with pytest.raises(QRCodeError, match="Invalid error correction level"):
            QRGenerator(error_correction="X")

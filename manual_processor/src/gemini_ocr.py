"""
Gemini OCR Processor
Handles OCR processing using Gemini 3.1 Flash Lite multimodal capabilities
"""

import logging
from typing import Optional
from pathlib import Path
from PIL import Image
from tenacity import retry, stop_after_attempt, wait_exponential

try:
    from google import genai
    _HAS_GENAI = True
except ImportError:
    _HAS_GENAI = False
    import google.generativeai as genai

from src.exceptions import OCRError

logger = logging.getLogger(__name__)


class GeminiOCRProcessor:
    """Handles OCR processing using Gemini 3.1 Flash Lite multimodal capabilities"""
    
    def __init__(self, api_key: str):
        """
        Initialize Gemini OCR processor
        
        Args:
            api_key: Google AI Studio API key
        """
        self.api_key = api_key
        if _HAS_GENAI:
            self.client = genai.Client(api_key=self.api_key)
            self.model_name = 'gemini-1.5-flash'
        else:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
        logger.info("Gemini OCR Processor initialized")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True
    )
    def extract_text(self, image: Image.Image) -> str:
        """
        Extract text from image using Gemini 3.1 Flash Lite
        
        Args:
            image: PIL Image object
            
        Returns:
            Extracted text string
        """
        try:
            # Prepare the prompt for OCR
            prompt = """
            この画像から日本語テキストを抽出してください。
            手書き文字、印刷体、英語、数字、図表の説明文をすべて含めてください。
            マークダウン形式で出力せず、プレーンテキストとして返してください。
            画像にテキストがない場合は空の文字列を返してください。
            """
            
            if _HAS_GENAI:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=[prompt, image]
                )
            else:
                response = self.model.generate_content([prompt, image])
            
            return response.text if response.text else ""
            
        except Exception as e:
            logger.error(f"OCR processing failed: {e}")
            raise OCRError(f"OCR processing failed: {e}") from e
    
    def extract_text_from_pdf_page(self, pdf_path: Path, page_number: int) -> str:
        """
        Extract text from a specific PDF page
        
        Args:
            pdf_path: Path to PDF file
            page_number: Page number to extract (1-indexed)
            
        Returns:
            Extracted text string
        """
        try:
            from src.pdf_processor import extract_images_from_pdf
            
            images = extract_images_from_pdf(pdf_path, dpi=300)
            if page_number < 1 or page_number > len(images):
                raise ValueError(f"Invalid page number: {page_number}")
            
            img = images[page_number - 1]
            return self.extract_text(img)
            
        except Exception as e:
            logger.error(f"Failed to extract text from PDF page: {e}")
            raise OCRError(f"Failed to extract text from PDF page: {e}") from e
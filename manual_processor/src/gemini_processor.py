"""
Gemini Processor Module
Handles text processing using Google Gemini API
"""

import logging
from typing import List, Optional, Literal
from dataclasses import dataclass, field
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

try:
    from google import genai
    _HAS_GENAI = True
except ImportError:
    _HAS_GENAI = False
    import google.generativeai as genai

from src.exceptions import GeminiAPIError, ProcessingError
from src.models import Section

logger = logging.getLogger(__name__)


@dataclass
class GeminiResult:
    """Result from Gemini API processing"""
    summary: str
    key_points: List[str]
    sections: List[Section]
    difficulty_level: Literal['beginner', 'intermediate', 'advanced'] = 'beginner'
    title: str = ""
    glossary: List[dict] = field(default_factory=list)  # List of {'term': str, 'explanation': str}


class GeminiProcessor:
    """Processor for Google Gemini API text processing"""
    
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-1.5-flash",
                 temperature: float = 0.3, max_output_tokens: int = 2048):
        """
        Initialize GeminiProcessor
        
        Args:
            api_key: Google AI Studio API key
            model_name: Gemini model name (default: gemini-1.5-flash)
            temperature: Generation temperature (0.0-1.0)
            max_output_tokens: Maximum output tokens
        """
        import os
        effective_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not effective_key:
            raise GeminiAPIError("Gemini APIキーが設定されていません")

        self.api_key = effective_key
        self.model_name = model_name
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        
        try:
            if _HAS_GENAI:
                self.client = genai.Client(api_key=self.api_key)
            else:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(model_name)
            logger.info(f"GeminiProcessor initialized with model: {model_name}")
        except Exception as e:
            if isinstance(e, GeminiAPIError):
                raise e
            logger.error(f"Failed to initialize GeminiProcessor: {e}")
            raise GeminiAPIError(f"Gemini API initialization failed: {str(e)}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        retry=retry_if_exception_type((Exception,)),
        reraise=True
    )
    def _generate_with_retry(self, prompt: str) -> str:
        """Internal helper with retry support for API calls"""
        try:
            if _HAS_GENAI:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt
                )
                return response.text.strip() if response.text else ""
            else:
                response = self.model.generate_content(prompt)
                return response.text.strip() if response.text else ""
        except Exception as e:
            logger.error(f"Gemini API call failed: {e}")
            raise GeminiAPIError(f"Gemini API call failed: {str(e)}")

    def _chunk_text(self, text: str, max_tokens: int = 4000) -> List[str]:
        """
        Split text into manageable chunks based on character/token count (Step 9)
        """
        if not text or not text.strip():
            return []
        
        if max_tokens <= 100:
            max_chars = (len(text) // 2) + 10
        else:
            max_chars = max_tokens * 4

        if len(text) <= max_chars:
            return [text]
        
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = []
        current_len = 0
        
        for para in paragraphs:
            para_len = len(para) + 2
            if current_len + para_len > max_chars and current_chunk:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = [para]
                current_len = para_len
            else:
                current_chunk.append(para)
                current_len += para_len
        
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))
        
        return chunks

    def generate_title(self, text: str) -> str:
        """テキストから初心者にもわかりやすいマニュアルタイトルを自動生成"""
        if not text or not text.strip():
            return "処理済みマニュアル"
        try:
            prompt = f"""
            以下のテキストの内容を読み取り、初心者でも一目で何のドキュメントか分かる簡潔で適切な「マニュアルのタイトル」を1つ生成してください。
            記号や余計な解説は省き、タイトル名のみを出力してください。
            
            テキスト:
            {text[:1500]}
            """
            result_text = self._generate_with_retry(prompt).strip()
            import re
            title = re.sub(r'^[【「\[\(]*(.*?)[】」\]\)]*$', r'\1', result_text)
            return title if title else "手書き整理マニュアル"
        except Exception as e:
            logger.warning(f"タイトル自動生成失敗: {e}")
            return "手書き整理マニュアル"

    def summarize_text(self, text: str, target_audience: str = "beginner", max_tokens: int = 4000, cancel_token = None) -> str:
        """
        Summarize text for target audience, handling chunks if text is long.
        """
        if not text or not text.strip():
            return ""
        
        try:
            chunks = self._chunk_text(text, max_tokens=max_tokens)
            summaries = []
            
            for chunk in chunks:
                if cancel_token is not None and hasattr(cancel_token, 'throw_if_cancelled'):
                    cancel_token.throw_if_cancelled()
                prompt = f"以下のテキストを{target_audience}向けに要約してください:\n\n{chunk}"
                summary_chunk = self._generate_with_retry(prompt)
                if summary_chunk:
                    summaries.append(summary_chunk)
            
            return "\n\n".join(summaries)
            
        except Exception as e:
            if cancel_token is not None and hasattr(cancel_token, 'is_cancelled') and cancel_token.is_cancelled:
                raise
            logger.error(f"Text summarization failed: {e}")
            raise GeminiAPIError(f"テキスト要約に失敗しました: {str(e)}")
    
    def extract_key_points(self, text: str, max_points: int = 10, cancel_token = None) -> List[str]:
        """
        Extract key points from text
        """
        if not text or not text.strip():
            return []
        
        if cancel_token is not None and hasattr(cancel_token, 'throw_if_cancelled'):
            cancel_token.throw_if_cancelled()

        prompt = f"""以下のテキストから重要なポイントを最大{max_points}個、箇条書きで抽出してください。

出力形式:
- ポイント1
- ポイント2

テキスト:
{text}"""
        try:
            result_text = self._generate_with_retry(prompt)
            lines = result_text.split('\n')
            key_points = []
            
            import re
            for line in lines:
                line_s = line.strip()
                if line_s:
                    clean_point = re.sub(r'^(?:[-•*]|\d+\.)\s*', '', line_s).strip()
                    if clean_point and clean_point not in key_points:
                        key_points.append(clean_point)
                        if len(key_points) >= max_points:
                            break
            
            return key_points[:max_points]
            
        except Exception as e:
            if cancel_token is not None and hasattr(cancel_token, 'is_cancelled') and cancel_token.is_cancelled:
                raise
            logger.error(f"Key point extraction failed: {e}")
            raise GeminiAPIError(f"キーポイント抽出に失敗しました: {str(e)}")

    
    def process_document(self, text: str, target_audience: str = "beginner", cancel_token = None) -> GeminiResult:
        """
        Process document to get summary, key points, and structure
        """
        if cancel_token is not None and hasattr(cancel_token, 'throw_if_cancelled'):
            cancel_token.throw_if_cancelled()

        if not text or not text.strip():
            return GeminiResult(
                summary="",
                key_points=[],
                sections=[],
                difficulty_level=target_audience,
                title=""
            )
        
        try:
            summary = self.summarize_text(text, target_audience=target_audience, cancel_token=cancel_token)
            key_points = self.extract_key_points(text, max_points=10, cancel_token=cancel_token)
            
            sections = [
                Section(title="概要", content=summary),
                Section(title="重要ポイント", content="\n".join(key_points))
            ]
            
            return GeminiResult(
                summary=summary,
                key_points=key_points,
                sections=sections,
                difficulty_level=target_audience,
                title="手書き整理マニュアル"
            )
        except GeminiAPIError:
            raise
        except Exception as e:
            if cancel_token is not None and hasattr(cancel_token, 'is_cancelled') and cancel_token.is_cancelled:
                raise
            logger.error(f"Document processing failed: {e}")
            raise GeminiAPIError(f"ドキュメント処理に失敗しました: {str(e)}")

    
    def _convert_sections(self, sections_data: list) -> List[Section]:
        """Convert JSON section data to Section dataclass objects"""
        result = []
        for sec in sections_data or []:
            subsections = None
            if sec.get('subsections'):
                subsections = self._convert_sections(sec['subsections'])
            
            result.append(Section(
                title=sec.get('title', ''),
                content=sec.get('content', ''),
                subsections=subsections
            ))
        return result
    
    def _process_document_text_markers(self, text: str) -> GeminiResult:
        """Fallback text-marker parser for process_document"""
        prompt = f"""
        あなたは初心者に優しく教えるエキスパートインストラクターです。
        以下の手書きスキャンテキストを読み取り、初心者向けに完全整理・再構成して以下のフォーマットで出力してください。

        [TITLE]
        初心者にもわかりやすいマニュアルのタイトル（1行）

        [SUMMARY]
        このマニュアルの全体像と目的を親しみやすい言葉で2-3文で説明してください。

        [KEY_POINTS]
        - 初心者がまず覚えるべき重要ポイントや注意点（箇条書き）

        [SECTIONS]
        ## 1. 準備・必要なもの
        内容を分かりやすく記述

        ## 2. 実行手順
        順番にステップバイステップで記述

        ## 3. トラブルシューティング・注意点
        困ったときの対応を記述

        [GLOSSARY]
        - 専門用語: 初心者向けの易しい解説

        テキスト:
        {text}"""
        
        result_text = self._generate_with_retry(prompt)
        
        title = "手書き整理マニュアル"
        summary = ""
        key_points = []
        sections = []
        glossary = []
        
        import re
        
        if "[TITLE]" in result_text:
            parts = result_text.split("[TITLE]")
            rest = parts[1]
            
            if "[SUMMARY]" in rest:
                title_part, rest = rest.split("[SUMMARY]", 1)
                title = title_part.strip().split('\n')[0].strip()
                title = re.sub(r'^[【「\[\(]*(.*?)[】」\]\)]*$', r'\1', title)
                
                if "[KEY_POINTS]" in rest:
                    summary_part, rest = rest.split("[KEY_POINTS]", 1)
                    summary = summary_part.strip()
                    
                    if "[SECTIONS]" in rest:
                        keypoints_part, rest = rest.split("[SECTIONS]", 1)
                        for line in keypoints_part.strip().split('\n'):
                            line_s = line.strip()
                            if line_s.startswith('- ') or line_s.startswith('• '):
                                point = line_s[2:].strip()
                                if point:
                                    key_points.append(point)
                        
                        if "[GLOSSARY]" in rest:
                            sections_part, glossary_part = rest.split("[GLOSSARY]", 1)
                            
                            for line in glossary_part.strip().split('\n'):
                                if ':' in line or '：' in line:
                                    sep = ':' if ':' in line else '：'
                                    term_parts = line.split(sep, 1)
                                    term = re.sub(r'^[-•*]\s*', '', term_parts[0]).strip()
                                    exp = term_parts[1].strip()
                                    if term and exp:
                                        glossary.append({'term': term, 'explanation': exp})
                        else:
                            sections_part = rest
                        
                        current_section = None
                        for line in sections_part.strip().split('\n'):
                            if line.startswith('## '):
                                if current_section:
                                    sections.append(current_section)
                                sec_title = line[3:].strip()
                                current_section = {'title': sec_title, 'content': []}
                            elif current_section is not None:
                                if line.strip():
                                    current_section['content'].append(line.strip())
                        if current_section:
                            sections.append(current_section)
                        
                        for section in sections:
                            section['content'] = '\n'.join(section['content'])
        
        if not title:
            title = self.generate_title(text)
        
        return GeminiResult(
            title=title,
            summary=summary,
            key_points=key_points,
            sections=self._convert_sections(sections) if sections else [],
            glossary=glossary
        )
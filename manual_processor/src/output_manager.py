# manual_processor/src/output_manager.py
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass

from .gemini_processor import GeminiResult
from .pdf_generator import create_formatted_pdf
from .docx_generator import create_word_document
from .audio_generator import AudioGenerator
from .exceptions import PDFGenerationError, DocxGenerationError, TTSError
from .utils.result_formatter import format_to_markdown
from .qr_generator import QRGenerator, QRCodeError

logger = logging.getLogger(__name__)

@dataclass
class OutputFiles:
    """生成された出力ファイル情報"""
    pdf_path: Path
    docx_path: Path
    audio_path: Path
    metadata: Dict[str, Any]
    qr_path: Optional[Path] = None
    diagram_markdown_path: Optional[Path] = None
    diagram_mermaid_path: Optional[Path] = None

@dataclass
class OutputConfig:
    """出力設定"""
    output_directory: Path
    base_name: str
    include_pdf: bool = True
    include_docx: bool = True
    include_audio: bool = True
    include_qr: bool = True
    include_diagram_markdown: bool = True
    include_diagram_mermaid: bool = True
    language_code: str = "ja-JP"
    voice_name: str = "ja-JP-Standard-A"
    speaking_rate: float = 1.0
    pitch: float = 0.0
    base_url: str = "http://localhost:8000"

def _extract_audio_text(content: Any, formatted_text: str) -> str:
    """音声合成用テキストを抽出するヘルパー関数"""
    if getattr(content, 'key_points', None):
        return "\n".join(content.key_points)
    if getattr(content, 'summary', None):
        return content.summary
    return formatted_text

def save_all_formats(content: GeminiResult, base_output_path: Path,
                     config: OutputConfig,
                     title: str = "処理済みマニュアル",
                     compact_layout: bool = False,
                     use_emojis: bool = False,
                     file_id: Optional[str] = None) -> OutputFiles:
    """
    すべての出力形式（PDF, Word, Audio）を一括で保存するメイン関数
    """
    # 出力ディレクトリの作成
    config.output_directory.mkdir(parents=True, exist_ok=True)
    
    # 出力ファイルパスの生成
    base_name = config.base_name or base_output_path.stem
    pdf_path = config.output_directory / f"{base_name}.pdf"
    docx_path = config.output_directory / f"{base_name}.docx"
    audio_path = config.output_directory / f"{base_name}.mp3"
    
    errors = []
    formatted_text = format_to_markdown(content)
    
    # QRコード生成
    qr_path = None
    if config.include_qr and file_id:
        try:
            qr_generator = QRGenerator()
            playback_url = f"{config.base_url.rstrip('/')}/api/download/{file_id}/audio"
            qr_output = config.output_directory / f"{base_name}_qr.png"
            qr_path = qr_generator.generate_qr(playback_url, qr_output, title=title)
            logger.info(f"QRコード生成完了: {qr_path}")
        except QRCodeError as e:
            logger.warning(f"QRコード生成失敗（処理は続行）: {e}")
        except Exception as e:
            logger.warning(f"QRコード生成中の予期せぬエラー: {e}")
    
    # 音声生成
    if config.include_audio:
        try:
            audio_generator = AudioGenerator(
                language_code=config.language_code,
                voice_name=config.voice_name,
                speaking_rate=config.speaking_rate,
                pitch=config.pitch
            )
            audio_text = _extract_audio_text(content, formatted_text)
            audio_path = audio_generator.generate_audio(audio_text, audio_path)
            logger.info(f"音声出力完了: {audio_path}")
        except TTSError as e:
            logger.error(f"音声生成失敗: {e}")
            errors.append(f"Audio: {str(e)}")
        except Exception as e:
            logger.error(f"音声生成中の予期せぬエラー: {e}")
            errors.append(f"Audio: 予期せぬエラー - {str(e)}")
    
    # PDF生成
    if config.include_pdf:
        try:
            pdf_path = create_formatted_pdf(formatted_text, pdf_path, title, compact_layout=compact_layout, use_emojis=use_emojis, qr_image_path=qr_path)
            logger.info(f"PDF出力完了: {pdf_path}")
        except PDFGenerationError as e:
            logger.error(f"PDF生成失敗: {e}")
            errors.append(f"PDF: {str(e)}")
        except Exception as e:
            logger.error(f"PDF生成中の予期せぬエラー: {e}")
            errors.append(f"PDF: 予期せぬエラー - {str(e)}")
    
    # Word文書生成
    if config.include_docx:
        try:
            docx_path = create_word_document(formatted_text, docx_path, title, compact_layout=compact_layout, use_emojis=use_emojis, qr_image_path=qr_path)
            logger.info(f"Word出力完了: {docx_path}")
        except DocxGenerationError as e:
            logger.error(f"Word生成失敗: {e}")
            errors.append(f"Word: {str(e)}")
        except Exception as e:
            logger.error(f"Word生成中の予期せぬエラー: {e}")
            errors.append(f"Word: 予期せぬエラー - {str(e)}")
    
    # エラーがあれば警告を出す
    if errors:
        logger.warning(f"出力生成でエラーが発生: {errors}")
    
    # メタデータの作成
    metadata = {
        "source_file": str(base_output_path),
        "processed_at": str(Path(base_output_path).stat().st_mtime) if base_output_path.exists() else 0,
        "page_count": len(getattr(content, 'sections', [])) if hasattr(content, 'sections') else 0,
        "word_count": len(getattr(content, 'summary', '')) if hasattr(content, 'summary') else len(formatted_text),
        "key_point_count": len(getattr(content, 'key_points', [])) if hasattr(content, 'key_points') else 0,
        "errors": errors if errors else []
    }
    
    return OutputFiles(
        pdf_path=pdf_path,
        docx_path=docx_path,
        audio_path=audio_path,
        qr_path=qr_path,
        metadata=metadata,
        diagram_markdown_path=None,
        diagram_mermaid_path=None
    )

def save_single_format(content: Any, output_path: Path,
                       format_type: str,
                       title: str = "処理済みマニュアル",
                       compact_layout: bool = False,
                       use_emojis: bool = False,
                       file_id: Optional[str] = None) -> Path:
    """
    単一の出力形式のみを保存する関数
    """
    format_type = format_type.lower()
    formatted_text = format_to_markdown(content)
    
    if format_type == 'pdf':
        return create_formatted_pdf(formatted_text, output_path, title, compact_layout=compact_layout, use_emojis=use_emojis)
    elif format_type == 'docx':
        return create_word_document(formatted_text, output_path, title, compact_layout=compact_layout, use_emojis=use_emojis)
    elif format_type == 'audio':
        audio_generator = AudioGenerator()
        audio_text = _extract_audio_text(content, formatted_text)
        return audio_generator.generate_audio(audio_text, output_path)
    elif format_type == 'diagram_markdown':
        from src.diagram_generator import DiagramGenerator
        gen = DiagramGenerator.__new__(DiagramGenerator)
        mermaid_code = content if isinstance(content, str) else getattr(content, 'mermaid_code', '')
        return gen.save_as_markdown(mermaid_code, output_path, title=title)
    elif format_type == 'diagram_mermaid':
        from src.diagram_generator import DiagramGenerator
        gen = DiagramGenerator.__new__(DiagramGenerator)
        mermaid_code = content if isinstance(content, str) else getattr(content, 'mermaid_code', '')
        return gen.save_as_mermaid(mermaid_code, output_path)
    else:
        raise ValueError(f"サポートされていない出力形式です: {format_type}")
# manual_processor/src/pdf_processor.py
import pypdfium2 as pdfium
from pypdf import PdfReader
from pathlib import Path
from typing import List
from PIL import Image
import logging

logger = logging.getLogger(__name__)

def extract_images_from_pdf(pdf_path: Path, dpi: int = 300) -> List[Image.Image]:
    """
    PDFからページごとに画像を抽出する
    
    Args:
        pdf_path: 処理対象のPDFファイルパス
        dpi: 画像変換時の解像度 (default=300)
    
    Returns:
        ページごとのPIL Imageオブジェクトのリスト
    
    Raises:
        FileNotFoundError: PDFファイルが見つからない場合
        ValueError: PDFファイルが破損している場合または処理に失敗した場合
    """
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDFファイルが見つかりません: {pdf_path}")
    
    images = []
    pdf = None
    try:
        # PDFドキュメントを開く
        pdf = pdfium.PdfDocument(str(pdf_path))
        page_count = len(pdf)
        logger.info(f"PDFを開きました: {pdf_path} (ページ数: {page_count})")
        
        scale = dpi / 72.0
        for page_number in range(page_count):
            page = pdf[page_number]
            # 画像としてレンダリング (PIL Image)
            img = page.render(scale=scale).to_pil()
            images.append(img)
            logger.debug(f"ページ {page_number + 1} の画像を抽出しました (サイズ: {img.size})")
        
        logger.info(f"PDFから {len(images)} ページの画像を抽出しました")
        return images
        
    except Exception as e:
        for img in images:
            try:
                img.close()
            # nosec B110: リソースクローズ処理のフェイルオーバー
            except Exception:
                pass
        logger.error(f"PDFからの画像抽出中にエラーが発生: {e}")
        raise ValueError(f"PDFファイルの処理に失敗しました: {pdf_path}") from e
    finally:
        if pdf:
            pdf.close()

def get_pdf_metadata(pdf_path: Path) -> dict:
    """
    PDFのメタデータ（ページ数、タイトル、作者など）を取得
    
    Args:
        pdf_path: 処理対象のPDFファイルパス
    
    Returns:
        メタデータを含む辞書
    """
    metadata = {
        "page_count": 0,
        "title": "",
        "author": "",
        "subject": "",
        "keywords": "",
        "creation_date": None,
        "modification_date": None,
        "file_size": 0
    }
    
    if not pdf_path.is_file():
        logger.warning(f"PDFファイルが見つかりません: {pdf_path}")
        return metadata
    
    try:
        # ファイルサイズ
        metadata["file_size"] = pdf_path.stat().st_size
        
        reader = PdfReader(str(pdf_path))
        metadata["page_count"] = len(reader.pages)
        
        # メタデータ取得
        meta = reader.metadata
        if meta:
            metadata["title"] = meta.title or ""
            metadata["author"] = meta.author or ""
            metadata["subject"] = meta.subject or ""
            metadata["keywords"] = getattr(meta, "keywords", "") or ""
            metadata["creation_date"] = str(meta.creation_date) if meta.creation_date else ""
            metadata["modification_date"] = str(meta.modification_date) if meta.modification_date else ""
        
        logger.debug(f"PDFメタデータを取得しました: {pdf_path}")
        return metadata
        
    except Exception as e:
        logger.error(f"PDFメタデータ取得中にエラーが発生: {e}")
        metadata["file_size"] = pdf_path.stat().st_size if pdf_path.is_file() else 0
        return metadata

def is_pdf_valid(pdf_path: Path) -> bool:
    """
    PDFファイルが有効かどうかをチェック
    
    Args:
        pdf_path: チェック対象のPDFファイルパス
    
    Returns:
        bool: 有効なPDFファイルの場合True、それ以外の場合False
    """
    if not pdf_path.is_file():
        logger.debug(f"ファイルが存在しません: {pdf_path}")
        return False
    
    if pdf_path.stat().st_size == 0:
        logger.debug(f"ファイルサイズが0バイトです: {pdf_path}")
        return False
    
    try:
        reader = PdfReader(str(pdf_path))
        is_valid = len(reader.pages) > 0
        logger.debug(f"PDFバリデーション結果: {pdf_path} -> {is_valid}")
        return is_valid
    except Exception as e:
        logger.debug(f"PDFファイルが無効です: {pdf_path} - エラー: {e}")
        return False

def process_pdf_with_progress(pdf_path: Path, dpi: int = 300, 
                             progress_callback: callable = None) -> List[Image.Image]:
    """
    プログレスコールバック付きのPDF処理関数
    
    Args:
        pdf_path: 処理対象のPDFファイルパス
        dpi: 画像変換時の解像度 (default=300)
        progress_callback: 進捗を報告するコールバック関数
                          シグニチャ: callback(current_page, total_pages)
    
    Returns:
        ページごとのPIL Imageオブジェクトのリスト
    
    Raises:
        FileNotFoundError: PDFファイルが見つからない場合
        ValueError: PDFファイルが破損している場合または処理に失敗した場合
    """
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDFファイルが見つかりません: {pdf_path}")
    
    images = []
    pdf = None
    try:
        pdf = pdfium.PdfDocument(str(pdf_path))
        total_pages = len(pdf)
        logger.info(f"プログレッサブルPDF処理開始: {pdf_path} (総ページ数: {total_pages})")
        
        scale = dpi / 72.0
        for page_number in range(total_pages):
            page = pdf[page_number]
            img = page.render(scale=scale).to_pil()
            images.append(img)
            
            # 進捗を報告
            if progress_callback:
                try:
                    progress_callback(page_number + 1, total_pages)
                except Exception as e:
                    logger.warning(f"進捗コールバックでエラーが発生: {e}")
            
            logger.debug(f"ページ {page_number + 1}/{total_pages} を処理しました")
        
        pdf.close()
        logger.info(f"プログレッサブルPDF処理完了: {len(images)} ページを処理しました")
        return images
        
    except Exception as e:
        logger.error(f"プログレッサブルPDF処理中にエラーが発生: {e}")
        raise ValueError(f"PDFファイルの処理に失敗しました: {pdf_path}") from e
"""
Processor Module
Main processing logic integrating OCR, summarization, and output generation
"""

import logging
from pathlib import Path
from typing import Dict, Optional

from config import Config
from src.ocr_processor import OCRProcessor
from src.gemini_processor import GeminiProcessor, GeminiResult, Section
from src.processor.processor_factory import ProcessorFactory
from src.pdf_generator import create_formatted_pdf
from src.docx_generator import create_word_document
from src.audio_generator import create_audio_summary
from src.diagram_generator import DiagramGenerator
from src.prompt_engine.prompt_builder import HandwrittenPromptBuilder
from src.security_manager import SecurityManager

logger = logging.getLogger(__name__)


def _sections_to_dicts(sections) -> list:
    """Convert Section objects (or dicts) to list of dicts for compatibility"""
    result = []
    for sec in sections or []:
        if isinstance(sec, dict):
            result.append(sec)
        elif isinstance(sec, Section):
            result.append({'title': sec.title, 'content': sec.content})
        else:
            result.append({'title': str(sec), 'content': ''})
    return result


class DocumentProcessor:
    """Main document processor"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config.get_instance()
        self.prompt_builder = HandwrittenPromptBuilder.from_config(self.config)
        self.ocr_processor = OCRProcessor(
            api_key=self.config.google_api_key,
            prompt_builder=self.prompt_builder,
        )
        self.summarizer = ProcessorFactory.create_processor(self.config)
        self.diagram_generator = DiagramGenerator(
            api_key=self.config.gemini_api_key,
            model_name=getattr(self.config, 'summary_model', getattr(self.config, 'gemini_model_name', 'gemini-1.5-flash'))
        )
        logger.info("DocumentProcessor initialized")

    
    def process_pdf(self, pdf_path: Path, compact_layout: bool = False, use_emojis: bool = False,
                    progress_tracker = None, cancel_token = None,
                    file_id: Optional[str] = None, base_url: str = "http://localhost:8000") -> Dict:
        """
        Process a PDF file through the complete pipeline with progress tracking and cancellation support
        """
        import time
        start_time = time.time()

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        if cancel_token is not None and hasattr(cancel_token, 'throw_if_cancelled'):
            cancel_token.throw_if_cancelled()

        if progress_tracker:
            progress_tracker.update("init", 5.0, f"入力検証中: {pdf_path.name}")

        # Step 6: Input Validation
        file_size_mb = pdf_path.stat().st_size / (1024 * 1024)
        if file_size_mb > self.config.max_file_size_mb:
            elapsed = time.time() - start_time
            logger.info(f"処理失敗: {pdf_path.name} ({elapsed:.1f}秒)")
            return {
                "success": False,
                "input_file": str(pdf_path),
                "error": f"ファイルサイズ ({file_size_mb:.1f}MB) が上限 ({self.config.max_file_size_mb}MB) を超えています"
            }

        if pdf_path.suffix.lower() not in self.config.supported_extensions:
            elapsed = time.time() - start_time
            logger.info(f"処理失敗: {pdf_path.name} ({elapsed:.1f}秒)")
            return {
                "success": False,
                "input_file": str(pdf_path),
                "error": f"サポートされていないファイル形式です: {pdf_path.suffix}"
            }
        
        try:
            logger.info(f"Starting processing of {pdf_path}")
            
            # Step 1: Extract text from PDF using OCR
            if progress_tracker:
                progress_tracker.update("ocr", 15.0, f"OCR処理中: {pdf_path.name}")
            extracted_text = self._extract_text_from_pdf(pdf_path, progress_tracker=progress_tracker, cancel_token=cancel_token)
            logger.info(f"OCR completed: {len(extracted_text)} characters extracted")
            
            if cancel_token is not None and hasattr(cancel_token, 'throw_if_cancelled'):
                cancel_token.throw_if_cancelled()

            # Step 1.5: Apply PII masking if enabled
            if getattr(self.config, 'pii_masking_enabled', False):
                masked_text, mask_info = SecurityManager.mask_sensitive_data(extracted_text, record_positions=True)
                if mask_info.get("counts"):
                    logger.info(f"PII masking applied: {mask_info['counts']}")
                extracted_text = masked_text
            
            # Step 2: Summarize and structure the text
            summary_result = self._run_summarization(extracted_text, pdf_path, progress_tracker=progress_tracker, cancel_token=cancel_token)
            
            if cancel_token is not None and hasattr(cancel_token, 'throw_if_cancelled'):
                cancel_token.throw_if_cancelled()

            # Step 3: Generate output files
            output_files = self._run_output_generation(summary_result, pdf_path, compact_layout=compact_layout, use_emojis=use_emojis, progress_tracker=progress_tracker,
                                                       file_id=file_id, base_url=base_url)
            
            if progress_tracker:
                progress_tracker.update("completed", 100.0, f"処理完了: {pdf_path.name}")

            elapsed = time.time() - start_time
            logger.info(f"処理完了: {pdf_path.name} ({elapsed:.1f}秒)")

            return {
                "success": True,
                "input_file": str(pdf_path),
                "title": summary_result.title or "手書きマニュアル",
                "extracted_text": extracted_text,
                "summary": summary_result.summary,
                "key_points": summary_result.key_points,
                "sections": _sections_to_dicts(summary_result.sections),
                "glossary": summary_result.glossary,
                "diagram_path": output_files.get("diagram"),
                "mermaid_code": output_files.get("mermaid_code", ""),
                "output_files": output_files
            }
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Processing failed for {pdf_path}: {e}")
            logger.info(f"処理失敗: {pdf_path.name} ({elapsed:.1f}秒)")
            return {
                "success": False,
                "input_file": str(pdf_path),
                "error": str(e)
            }
            
    def _run_summarization(self, extracted_text: str, pdf_path: Path, progress_tracker = None, cancel_token = None) -> GeminiResult:
        """AIによる要約・構造化を実行"""
        if progress_tracker:
            progress_tracker.update("summarize", 50.0, f"AI要約・構成生成中: {pdf_path.name}")
        
        if hasattr(self.summarizer, 'process_document'):
            import inspect
            sig = inspect.signature(self.summarizer.process_document)
            if 'cancel_token' in sig.parameters:
                summary_result = self.summarizer.process_document(extracted_text, cancel_token=cancel_token)
            else:
                summary_result = self.summarizer.process_document(extracted_text)
        else:
            summary_result = self.summarizer.process_document(extracted_text)
            
        logger.info(f"Summarization completed: {len(summary_result.key_points)} key points found")
        return summary_result

    def _run_output_generation(self, summary_result: GeminiResult, pdf_path: Path, compact_layout: bool = False, use_emojis: bool = False, progress_tracker = None,
                               file_id: Optional[str] = None, base_url: str = "http://localhost:8000") -> Dict[str, str]:
        """出力ファイル（PDF/Word/音声/図表）の生成を実行"""
        if progress_tracker:
            progress_tracker.update("output", 75.0, f"ファイル出力中 (PDF/Word/音声/図表): {pdf_path.name}")
        return self._generate_outputs(summary_result, pdf_path, compact_layout=compact_layout, use_emojis=use_emojis,
                                      file_id=file_id, base_url=base_url)

    def process_batch(self, pdf_paths: list, progress_tracker = None, cancel_token = None) -> list:
        """
        Process multiple PDF files sequentially
        """
        results = []
        for pdf_path in pdf_paths:
            if cancel_token is not None and hasattr(cancel_token, 'throw_if_cancelled'):
                cancel_token.throw_if_cancelled()
            path_obj = Path(pdf_path)
            if path_obj.exists() and path_obj.suffix.lower() == ".pdf":
                result = self.process_pdf(path_obj, progress_tracker=progress_tracker, cancel_token=cancel_token)
                results.append(result)
        return results

    def process_directory(self, dir_path: Path, recursive: bool = True, progress_tracker = None, cancel_token = None) -> list:
        """
        Process all PDF files inside a directory
        """
        if not dir_path.exists() or not dir_path.is_dir():
            raise NotADirectoryError(f"Directory not found: {dir_path}")
        
        pattern = "**/*.pdf" if recursive else "*.pdf"
        pdf_files = list(dir_path.glob(pattern))
        logger.info(f"Found {len(pdf_files)} PDF files in directory: {dir_path}")
        return self.process_batch(pdf_files, progress_tracker=progress_tracker, cancel_token=cancel_token)
    
    def _extract_text_from_pdf(self, pdf_path: Path, progress_tracker = None, cancel_token = None) -> str:
        """Extract text from all pages of a PDF (バッチ並列処理 + メモリ解放 + 部分失敗許容 + キャンセル対応)"""
        import io
        from PIL import Image
        from src.pdf_processor import extract_images_from_pdf
        from concurrent.futures import ThreadPoolExecutor, as_completed

        if cancel_token is not None and hasattr(cancel_token, 'throw_if_cancelled'):
            cancel_token.throw_if_cancelled()

        try:
            images = extract_images_from_pdf(pdf_path, dpi=self.config.pdf_dpi)
        except (FileNotFoundError, ValueError, OSError):
            # 一部テストやモック環境では実ファイルが存在しないまま fitz.open が使われることがある。
            # この場合は PyMuPDF のパスベースレンダリングへフォールバックし、ページ単位で OCR を継続する。
            try:
                import fitz

                with fitz.open(str(pdf_path)) as doc:
                    images = []
                    for page_number in range(doc.page_count):
                        page = doc.load_page(page_number)
                        pix = page.get_pixmap(matrix=fitz.Matrix(self.config.pdf_dpi / 72, self.config.pdf_dpi / 72))
                        img = Image.open(io.BytesIO(pix.tobytes("png")))
                        img.page_id = page_number + 1
                        images.append(img)
            except Exception:
                raise
        total_pages = len(images)
        if total_pages == 0:
            raise Exception(f"PDFから画像を抽出できませんでした: {pdf_path}")

        results = {}
        failed_pages = []
        batch_size = 4

        def ocr_page(page_num, img):
            try:
                if cancel_token is not None and hasattr(cancel_token, 'throw_if_cancelled'):
                    cancel_token.throw_if_cancelled()
                text = self.ocr_processor.extract_text(img)
                return page_num, (text if text.strip() else f"[ページ {page_num + 1}: テキストなし]"), None
            except Exception as e:
                logger.warning(f"ページ {page_num + 1}/{total_pages} のOCR失敗: {e}")
                return page_num, None, str(e)
            finally:
                try:
                    img.close()
                except Exception:
                    pass

        for start_idx in range(0, total_pages, batch_size):
            if cancel_token is not None and hasattr(cancel_token, 'throw_if_cancelled'):
                cancel_token.throw_if_cancelled()

            batch = [(start_idx + i, images[start_idx + i]) for i in range(min(batch_size, total_pages - start_idx))]
            max_workers = min(len(batch), 4)

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(ocr_page, pn, img): pn for pn, img in batch}
                for future in as_completed(futures):
                    if cancel_token is not None and hasattr(cancel_token, 'throw_if_cancelled'):
                        cancel_token.throw_if_cancelled()
                    page_num, text, err = future.result()
                    if text is None:
                        failed_pages.append((page_num + 1, err or "OCR Error"))
                        results[page_num] = f"[ページ {page_num + 1}: 読み取り失敗]"
                    else:
                        results[page_num] = text

        text_parts = [results[i] for i in range(total_pages)]

        if failed_pages:
            failed_info = [f"P{p}({err})" for p, err in failed_pages]
            logger.warning(f"OCR部分失敗: {len(failed_pages)}/{total_pages}ページ - {', '.join(failed_info)}")

        if not any(t.strip() and not t.startswith("[ページ") for t in text_parts):
            raise Exception(f"全ページのOCRに失敗しました: {pdf_path}")

        return "\n\n".join(text_parts)
    
    def _generate_outputs(self, summary_result: GeminiResult, pdf_path: Path, compact_layout: bool = False, use_emojis: bool = False,
                          file_id: Optional[str] = None, base_url: str = "http://localhost:8000") -> Dict[str, str]:
        """Generate PDF, Word, audio, and flowchart diagram output files"""
        import re
        output_dir = self.config.output_directory
        doc_title = summary_result.title or "処理済みマニュアル"
        
        # 安全なファイル名を生成
        safe_title = re.sub(r'[\\/:*?"<>|]', '_', doc_title).strip()
        base_name = f"{pdf_path.stem}_{safe_title}" if safe_title else pdf_path.stem
        
        # セクションをdict形式に変換（互換性維持）
        sections_dicts = _sections_to_dicts(summary_result.sections)
        
        # 整形テキストの構築
        content_lines = []
        content_lines.append(f"概要\n{summary_result.summary}\n")
        
        if summary_result.key_points:
            content_lines.append("## 初心者向け重要ポイント")
            for kp in summary_result.key_points:
                content_lines.append(f"- {kp}")
            content_lines.append("")
            
        for sec in sections_dicts:
            content_lines.append(f"## {sec['title']}")
            content_lines.append(sec['content'])
            content_lines.append("")
            
        glossary = summary_result.glossary or []
        if glossary:
            content_lines.append("## 用語集（解説）")
            for item in glossary:
                content_lines.append(f"- {item['term']}: {item['explanation']}")
            content_lines.append("")
            
        full_content_text = "\n".join(content_lines)
        outputs = {}

        # 1. Generate flowchart diagram FIRST
        diagram_path_obj = None
        diagram_markdown_path = None
        diagram_mermaid_path = None
        if self.config.generate_diagram:
            try:
                diagram_output = output_dir / f"{base_name}_フロー図.png" if self.config.generate_diagram_png else None
                diagram_md_output = output_dir / f"{base_name}_フロー図.md"
                diagram_mmd_output = output_dir / f"{base_name}_フロー図.mmd" if self.config.generate_diagram_mermaid else None
                diagram_result = self.diagram_generator.generate(
                    text=full_content_text,
                    sections=sections_dicts,
                    key_points=summary_result.key_points,
                    output_path=diagram_output,
                    theme=self.config.diagram_theme,
                    width=self.config.diagram_width,
                    height=self.config.diagram_height,
                    markdown_path=diagram_md_output,
                    mermaid_path=diagram_mmd_output
                )
                if diagram_result.success:
                    if diagram_result.image_path:
                        diagram_path_obj = diagram_result.image_path
                        outputs["diagram"] = str(diagram_result.image_path)
                    outputs["mermaid_code"] = diagram_result.mermaid_code
                    if diagram_result.markdown_path:
                        diagram_markdown_path = diagram_result.markdown_path
                        outputs["diagram_markdown"] = str(diagram_result.markdown_path)
                    if diagram_result.mermaid_path:
                        diagram_mermaid_path = diagram_result.mermaid_path
                        outputs["diagram_mermaid"] = str(diagram_result.mermaid_path)
                    logger.info(f"Diagram generated: {diagram_result.diagram_type}")
                else:
                    logger.warning(f"Diagram generation failed: {diagram_result.error_message}")
                    outputs["diagram"] = None
            except Exception as e:
                logger.warning(f"Diagram generation failed: {e}")
                outputs["diagram"] = None
        
        # 2. Generate PDF (with diagram image if present)
        try:
            pdf_output = output_dir / f"{base_name}.pdf"
            create_formatted_pdf(full_content_text, pdf_output, title=doc_title,
                                 compact_layout=compact_layout, use_emojis=use_emojis,
                                 diagram_path=diagram_path_obj)
            outputs["pdf"] = str(pdf_output)
            logger.info(f"PDF generated: {pdf_output}")
        except Exception as e:
            logger.warning(f"PDF generation failed: {e}")
            outputs["pdf"] = None
        
        # 3. Generate Word document (with diagram image if present)
        try:
            docx_output = output_dir / f"{base_name}.docx"
            create_word_document(full_content_text, docx_output, title=doc_title,
                                 compact_layout=compact_layout, use_emojis=use_emojis,
                                 diagram_path=diagram_path_obj)
            outputs["docx"] = str(docx_output)
            logger.info(f"Word document generated: {docx_output}")
        except Exception as e:
            logger.warning(f"Word generation failed: {e}")
            outputs["docx"] = None
        
        # 4. Generate audio - combine title, summary, and key points
        try:
            audio_text = f"【{doc_title}】\n\n{summary_result.summary}"
            if summary_result.key_points:
                audio_text += "\n\n重要なポイントをまとめます。\n" + "\n".join([f"ポイント: {point}" for point in summary_result.key_points])
            
            audio_output = output_dir / f"{base_name}.mp3"
            create_audio_summary(audio_text, audio_output)
            outputs["audio"] = str(audio_output)
            logger.info(f"Audio file generated: {audio_output}")
        except Exception as e:
            logger.warning(f"Audio generation failed: {e}")
            outputs["audio"] = None
        
        # 5. Generate QR code for audio playback (if file_id is available)
        qr_path = None
        if file_id and outputs.get("audio") and Path(outputs["audio"]).exists():
            try:
                from src.qr_generator import QRGenerator
                qr_gen = QRGenerator()
                playback_url = f"{base_url.rstrip('/')}/api/download/{file_id}/audio"
                qr_output = output_dir / f"{base_name}_qr.png"
                qr_path = qr_gen.generate_qr(playback_url, qr_output, title=doc_title)
                outputs["qr"] = str(qr_path)
                logger.info(f"QR code generated: {qr_path}")
            except Exception as e:
                logger.warning(f"QR code generation failed (continuing): {e}")
        
        # 2. Generate PDF (with diagram image and QR if present)
        try:
            pdf_output = output_dir / f"{base_name}.pdf"
            create_formatted_pdf(full_content_text, pdf_output, title=doc_title,
                                 compact_layout=compact_layout, use_emojis=use_emojis,
                                 diagram_path=diagram_path_obj,
                                 qr_image_path=qr_path)
            outputs["pdf"] = str(pdf_output)
            logger.info(f"PDF generated: {pdf_output}")
        except Exception as e:
            logger.warning(f"PDF generation failed: {e}")
            outputs["pdf"] = None
        
        # 3. Generate Word document (with diagram image and QR if present)
        try:
            docx_output = output_dir / f"{base_name}.docx"
            create_word_document(full_content_text, docx_output, title=doc_title,
                                 compact_layout=compact_layout, use_emojis=use_emojis,
                                 diagram_path=diagram_path_obj,
                                 qr_image_path=qr_path)
            outputs["docx"] = str(docx_output)
            logger.info(f"Word document generated: {docx_output}")
        except Exception as e:
            logger.warning(f"Word generation failed: {e}")
            outputs["docx"] = None
        
        return outputs
"""
FastAPI Web Server for Manual Processor
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path
from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from config.config import Config
from src.i18n_manager import I18nManager
from src.security_manager import SecurityManager, AuditLogger
from src.utils.validators import validate_pdf_content, validate_extension
from src.google_drive_manager import GoogleDriveManager, GoogleDriveError, DriveFile

logger = logging.getLogger(__name__)

config = Config.get_instance()
i18n_manager = I18nManager(default_lang=config.default_language)

BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="手書きマニュアル処理システム Web API",
    version="2.0.0",
    description="スキャンした手書きマニュアルのOCR解析・AI要約・マルチフォーマット生成Webサーバー"
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.web_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
    expose_headers=["Content-Disposition"],
    max_age=600,
)


class SetLanguageRequest(BaseModel):
    language: str


class ProcessOptions(BaseModel):
    compact_layout: bool = False
    use_emojis: bool = False
    prompt_layout: Optional[str] = None
    prompt_strict_mode: Optional[bool] = None
    prompt_has_diagrams: Optional[bool] = None
    prompt_low_quality_mode: Optional[bool] = None


class MermaidRenderRequest(BaseModel):
    mermaid_code: str
    theme: str = "default"
    width: int = 800
    height: int = 600


class MermaidRegenerateRequest(BaseModel):
    current_code: str
    instruction: str


@app.get("/")
async def serve_dashboard(request: Request):
    """Web UI ダッシュボード画面"""
    return templates.TemplateResponse(request, "index.html")


@app.get("/api/health")
async def health_check() -> Dict[str, str]:
    """サーバーの正常性確認エンドポイント"""
    return {
        "status": "ok",
        "version": "2.0.0",
        "processor_type": config.processor_type
    }


@app.get("/api/config")
async def get_public_config() -> Dict[str, Any]:
    """公開可能な設定情報を取得"""
    return {
        "gemini_model_name": config.gemini_model_name,
        "processor_type": config.processor_type,
        "pdf_dpi": config.pdf_dpi,
        "max_file_size_mb": config.max_file_size_mb,
        "web_upload_max_mb": config.web_upload_max_mb,
        "output_directory": str(config.output_directory),
        "supported_extensions": config.supported_extensions,
        "default_language": config.default_language
    }


@app.get("/api/i18n/languages")
async def get_available_languages() -> Dict[str, Any]:
    """利用可能な言語一覧を取得"""
    return {
        "languages": i18n_manager.get_available_languages(),
        "current": i18n_manager.current_lang
    }


@app.post("/api/i18n/set")
async def set_language(req: SetLanguageRequest) -> Dict[str, str]:
    """言語を設定"""
    i18n_manager.set_language(req.language)
    return {"status": "ok", "language": i18n_manager.current_lang}


@app.get("/api/i18n/translations/{lang}")
async def get_translations(lang: str) -> Dict[str, str]:
    """指定言語の翻訳を取得"""
    translations = i18n_manager.TRANSLATIONS.get(lang.lower())
    if not translations:
        raise HTTPException(status_code=404, detail=f"Language '{lang}' not found")
    return translations


@app.post("/api/i18n/detect")
async def detect_language_text(req: dict) -> Dict[str, str]:
    """テキストの言語を自動検出"""
    text = req.get("text", "")
    detected = i18n_manager.detect_language(text)
    return {"detected_language": detected}


@app.get("/api/security/status")
async def get_security_status() -> Dict[str, Any]:
    """セキュリティ設定・状態を取得"""
    import os as _os
    return {
        "pii_masking_enabled": getattr(config, "pii_masking_enabled", False),
        "encryption_available": True,
        "encryption_key_set": bool(_os.getenv("ENCRYPTION_KEY")),
        "keyring_available": True,
        "audit_log_enabled": True
    }


@app.get("/api/security/audit")
async def get_audit_logs(limit: int = 100) -> Dict[str, Any]:
    """監査ログを取得"""
    audit = AuditLogger()
    logs = audit.get_recent_logs(limit=limit)
    return {"logs": logs, "count": len(logs)}


@app.post("/api/security/mask")
async def mask_text(req: dict) -> Dict[str, Any]:
    """テキスト中の機密情報をマスク"""
    text = req.get("text", "")
    if not text:
        return {"masked_text": "", "counts": {}}

    masked, info = SecurityManager.mask_sensitive_data(text, record_positions=True)
    return {
        "masked_text": masked,
        "counts": info.get("counts", {}),
        "positions_count": len(info.get("positions", []))
    }


import uuid

# アップロード済みファイルのメタデータキャッシュ
UPLOADED_FILES: Dict[str, Dict[str, Any]] = {}

# 処理結果のインメモリキャッシュ
PROCESSING_RESULTS: Dict[str, Dict[str, Any]] = {}


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)) -> Dict[str, Any]:
    """PDF ファイルをアップロードして一元管理ディレクトリに保存"""
    # 拡張子チェック
    if not validate_extension(file.filename, [".pdf"]):
        raise HTTPException(status_code=400, detail="PDF ファイルのみアップロード可能です。")
    
    # Content-Type チェック
    content_type = file.content_type or ""
    if content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Content-Type が application/pdf ではありません。")
    
    file_bytes = await file.read()
    size_mb = len(file_bytes) / (1024 * 1024)
    
    # マジックバイトチェック
    if not validate_pdf_content(file_bytes):
        raise HTTPException(status_code=400, detail="ファイル内容がPDF形式ではありません。")
    
    # サイズチェック
    if size_mb > config.web_upload_max_mb:
        raise HTTPException(
            status_code=400,
            detail=f"ファイルサイズ ({size_mb:.1f}MB) が上限 ({config.web_upload_max_mb}MB) を超えています。"
        )
    
    file_id = uuid.uuid4().hex
    save_dir = config.temp_directory / file_id
    save_dir.mkdir(parents=True, exist_ok=True)
    file_path = save_dir / file.filename

    with open(file_path, "wb") as f:
        f.write(file_bytes)
    
    meta = {
        "file_id": file_id,
        "filename": file.filename,
        "size_mb": round(size_mb, 2),
        "path": str(file_path)
    }
    UPLOADED_FILES[file_id] = meta
    logger.info(f"Uploaded file saved: {file_path}")
    return meta


@app.get("/api/uploads")
async def list_uploads() -> Dict[str, Any]:
    """アップロード済みファイル一覧を取得"""
    return {"uploads": list(UPLOADED_FILES.values())}


from src.processor.processor import DocumentProcessor

PROCESSING_RESULTS: Dict[str, Dict[str, Any]] = {}


@app.post("/api/process/{file_id}")
async def process_pdf_api(file_id: str, options: ProcessOptions = ProcessOptions()) -> Dict[str, Any]:
    """アップロード済み PDF をパイプライン処理"""
    if file_id not in UPLOADED_FILES:
        raise HTTPException(status_code=404, detail="指定された file_id が存在しません。")
    
    file_info = UPLOADED_FILES[file_id]
    pdf_path = Path(file_info["path"])

    if options.prompt_layout in {"horizontal", "vertical"}:
        config.prompt_layout = options.prompt_layout
    if options.prompt_strict_mode is not None:
        config.prompt_strict_mode = options.prompt_strict_mode
    if options.prompt_has_diagrams is not None:
        config.prompt_has_diagrams = options.prompt_has_diagrams
    if options.prompt_low_quality_mode is not None:
        config.prompt_low_quality_mode = options.prompt_low_quality_mode

    processor = DocumentProcessor(config)
    base_url = getattr(config, 'base_url', 'http://localhost:8000')
    result = processor.process_pdf(
        pdf_path,
        compact_layout=options.compact_layout,
        use_emojis=options.use_emojis,
        file_id=file_id,
        base_url=base_url
    )

    PROCESSING_RESULTS[file_id] = result
    return result


@app.get("/api/results/{file_id}")
async def get_process_result(file_id: str) -> Dict[str, Any]:
    """処理結果を取得"""
    if file_id not in PROCESSING_RESULTS:
        raise HTTPException(status_code=404, detail="処理結果が見つかりません。")
    return PROCESSING_RESULTS[file_id]


from fastapi import WebSocket, WebSocketDisconnect
import asyncio

ACTIVE_WEBSOCKETS: Dict[str, WebSocket] = {}


@app.websocket("/ws/progress/{file_id}")
async def websocket_progress(websocket: WebSocket, file_id: str):
    """リアルタイム進捗通知 WebSocket"""
    await websocket.accept()
    ACTIVE_WEBSOCKETS[file_id] = websocket
    try:
        await websocket.send_json({"status": "connected", "file_id": file_id, "progress": 0, "stage": "接続完了"})
        while True:
            # 接続維持用 ping/pong 受信待機
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {file_id}")
    finally:
        ACTIVE_WEBSOCKETS.pop(file_id, None)


@app.get("/api/download/{file_id}/{file_type}")
async def download_file_api(file_id: str, file_type: str):
    """生成ファイルのダウンロード API (file_type: pdf, docx, audio, diagram, diagram_markdown, diagram_mermaid, all)"""
    if file_id not in PROCESSING_RESULTS:
        raise HTTPException(status_code=404, detail="処理結果が見つかりません。")
    
    res = PROCESSING_RESULTS[file_id]
    outputs = res.get("output_files", {})

    if file_type == "all":
        import zipfile
        from io import BytesIO
        from fastapi.responses import StreamingResponse

        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for key, path_str in outputs.items():
                if not path_str:
                    continue
                path = Path(path_str)
                if path.exists():
                    zipf.write(path, arcname=path.name)
        zip_buffer.seek(0)
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={file_id}_outputs.zip"}
        )

    target_path_str = outputs.get(file_type)
    if not target_path_str:
        if file_type == "diagram":
            target_path_str = outputs.get("diagram_markdown")
        if not target_path_str:
            raise HTTPException(status_code=404, detail=f"指定されたファイル ({file_type}) が存在しません。")

    file_path = Path(target_path_str)
    media_types = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "audio": "audio/mpeg",
        "diagram": "text/markdown",
        "diagram_markdown": "text/markdown",
        "diagram_mermaid": "text/plain"
    }

    return FileResponse(
        path=file_path,
        media_type=media_types.get(file_type, "application/octet-stream"),
        filename=file_path.name
    )


from src.diagram_generator import DiagramGenerator


@app.post("/api/mermaid/validate")
async def validate_mermaid(req: MermaidRenderRequest) -> Dict[str, Any]:
    """Mermaid.js コードの簡易構文検証"""
    code = req.mermaid_code.strip()
    if not code:
        return {"valid": False, "error": "コードが空です。"}
    
    valid_keywords = ["graph", "flowchart", "sequenceDiagram", "classDiagram", "gantt", "pie", "mindmap"]
    first_line = code.split("\n")[0].strip()
    is_valid = any(first_line.startswith(kw) for kw in valid_keywords)

    return {
        "valid": is_valid,
        "type": first_line.split()[0] if is_valid else "unknown"
    }


@app.post("/api/mermaid/render")
async def render_mermaid(req: MermaidRenderRequest):
    """Mermaid.js コードを PNG 画像にリアルタイムレンダリング"""
    import tempfile
    
    temp_dir = Path(tempfile.gettempdir())
    out_png = temp_dir / f"mermaid_render_{uuid.uuid4().hex[:8]}.png"

    diagram_gen = DiagramGenerator(api_key=config.gemini_api_key)
    try:
        rendered_path = diagram_gen.render_to_image(
            mermaid_code=req.mermaid_code,
            output_path=out_png,
            theme=req.theme,
            width=req.width,
            height=req.height
        )
        return FileResponse(path=rendered_path, media_type="image/png", filename="diagram.png")
    except Exception as e:
        logger.error(f"Mermaid rendering error: {e}")
        raise HTTPException(status_code=400, detail=f"レンダリング失敗: {str(e)}")


@app.post("/api/mermaid/regenerate")
async def regenerate_mermaid(req: MermaidRegenerateRequest) -> Dict[str, Any]:
    """自然言語指示に基づいて Mermaid.js フローチャートを AI で修正・再生成"""
    from src.gemini_processor import GeminiProcessor
    
    prompt = f"""以下の Mermaid.js フローチャートを、ユーザーの指示に従って修正・再生成してください。
返答は修正後の Mermaid.js コードのみを出力してください（説明文や余計なマークダウン記法は除外してください）。

【現在の Mermaid.js コード】
{req.current_code}

【修正指示】
{req.instruction}
"""
    try:
        processor = GeminiProcessor(api_key=config.gemini_api_key)
        new_code = processor.summarize_text(prompt)
        
        # 不要な ```mermaid マークダウンタグの除去
        clean_code = new_code.replace("```mermaid", "").replace("```", "").strip()
        return {"success": True, "mermaid_code": clean_code}
    except Exception as e:
        logger.error(f"AI Mermaid regeneration error: {e}")
        raise HTTPException(status_code=500, detail=f"AI 再生成エラー: {str(e)}")


@app.post("/api/mermaid/save/{file_id}")
async def save_mermaid_and_rebuild(file_id: str, req: MermaidRenderRequest) -> Dict[str, Any]:
    """編集・修正した Mermaid コードを保存し、PDF および Word ドキュメントを再生成"""
    if file_id not in PROCESSING_RESULTS:
        raise HTTPException(status_code=404, detail="処理結果が見つかりません。")
    
    res = PROCESSING_RESULTS[file_id]
    outputs = res.get("output_files", {})
    diagram_path_str = outputs.get("diagram")

    if not diagram_path_str:
        diagram_path_str = str(config.output_directory / f"diagram_{file_id}.png")

    diagram_path = Path(diagram_path_str) if diagram_path_str else None
    diagram_gen = DiagramGenerator(api_key=config.gemini_api_key)

    try:
        # 設定に応じて PNG 画像を生成
        if config.generate_diagram_png and diagram_path:
            rendered_path = diagram_gen.render_to_image(
                mermaid_code=req.mermaid_code,
                output_path=diagram_path,
                theme=req.theme,
                width=req.width,
                height=req.height
            )
            outputs["diagram"] = str(rendered_path)
        res["mermaid_code"] = req.mermaid_code

        # Markdown および Mermaid ファイルを保存
        if config.generate_diagram_markdown:
            diagram_md_path = config.output_directory / f"diagram_{file_id}.md"
            diagram_gen.save_as_markdown(req.mermaid_code, diagram_md_path, title=res.get("title", "フローチャート"))
            outputs["diagram_markdown"] = str(diagram_md_path)
        if config.generate_diagram_mermaid:
            diagram_mmd_path = config.output_directory / f"diagram_{file_id}.mmd"
            diagram_gen.save_as_mermaid(req.mermaid_code, diagram_mmd_path)
            outputs["diagram_mermaid"] = str(diagram_mmd_path)

        # PDF および Word の再生成
        from src.pdf_generator import create_formatted_pdf
        from src.docx_generator import create_word_document

        doc_title = res.get("title", "手書きマニュアル")
        content_text = f"概要\n{res.get('summary', '')}\n\n## 修正済みフロー図適用"

        pdf_path = outputs.get("pdf")
        if pdf_path:
            create_formatted_pdf(content_text, Path(pdf_path), title=doc_title, diagram_path=rendered_path)

        docx_path = outputs.get("docx")
        if docx_path:
            create_word_document(content_text, Path(docx_path), title=doc_title, diagram_path=rendered_path)

        return {"success": True, "message": "フロー図の保存とドキュメント再生成が完了しました。", "diagram_markdown": str(diagram_md_path), "diagram_mermaid": str(diagram_mmd_path)}
    except Exception as e:
        logger.error(f"Save & rebuild error: {e}")
        raise HTTPException(status_code=500, detail=f"再生成エラー: {str(e)}")


def _get_drive_manager() -> GoogleDriveManager:
    """Create GoogleDriveManager from config"""
    credentials_path = getattr(config.drive, 'credentials_path', None)
    if credentials_path:
        creds_path = Path(credentials_path)
    else:
        creds_path = Path(__file__).parent.parent.parent / "credentials.json"
    return GoogleDriveManager(credentials_path=creds_path)


@app.get("/api/drive/status")
async def drive_status() -> Dict[str, Any]:
    """Googleドライブ認証状態を取得"""
    try:
        manager = _get_drive_manager()
        return {
            "authenticated": manager.is_authenticated(),
            "enabled": getattr(config.drive, 'enabled', False),
        }
    except Exception as e:
        logger.error(f"Drive status check failed: {e}")
        return {"authenticated": False, "enabled": False, "error": str(e)}


@app.get("/api/drive/auth")
async def drive_auth_redirect() -> Dict[str, str]:
    """Google OAuth2認証URLを取得"""
    try:
        manager = _get_drive_manager()
        redirect_uri = f"http://localhost:{config.web.port}/api/drive/callback"
        auth_url = manager.get_authorization_url(redirect_uri=redirect_uri)
        return {"auth_url": auth_url}
    except GoogleDriveError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Drive auth URL generation failed: {e}")
        raise HTTPException(status_code=500, detail="認証URLの生成に失敗しました")


@app.get("/api/drive/callback")
async def drive_auth_callback(request: Request, code: Optional[str] = None) -> Dict[str, str]:
    """OAuth2コールバック（認証コードをトークンに交換）"""
    if not code:
        raise HTTPException(status_code=400, detail="認証コードがありません")
    try:
        manager = _get_drive_manager()
        redirect_uri = f"http://localhost:{config.web.port}/api/drive/callback"
        token_info = manager.exchange_code(code, redirect_uri=redirect_uri)
        return {"status": "ok", "message": "認証成功", "token_info": token_info}
    except GoogleDriveError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Drive auth callback failed: {e}")
        raise HTTPException(status_code=500, detail="認証処理に失敗しました")


@app.post("/api/drive/upload/{file_id}")
async def upload_to_drive(file_id: str) -> Dict[str, Any]:
    """処理結果をGoogleドライブにアップロード"""
    if file_id not in PROCESSING_RESULTS:
        raise HTTPException(status_code=404, detail="処理結果が見つかりません。")

    try:
        manager = _get_drive_manager()
        if not manager.is_authenticated():
            raise HTTPException(status_code=401, detail="Googleドライブに認証されていません。")

        res = PROCESSING_RESULTS[file_id]
        outputs = res.get("output_files", {})
        drive_urls = {}
        folder_id = getattr(config.drive, 'folder_id', None)
        share_public = getattr(config.drive, 'share_public', True)

        if not folder_id and getattr(config.drive, 'folder_name', None):
            try:
                folder_id = manager.create_folder(config.drive.folder_name)
            except Exception as e:
                logger.warning(f"Failed to create Drive folder: {e}")

        upload_map = {
            "pdf": ("application/pdf", outputs.get("pdf")),
            "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", outputs.get("docx")),
            "audio": ("audio/mpeg", outputs.get("audio")),
            "diagram": ("image/png", outputs.get("diagram")),
            "qr": ("image/png", outputs.get("qr")),
        }

        for key, (mime_type, path_str) in upload_map.items():
            if not path_str:
                continue
            path = Path(path_str)
            if not path.exists():
                continue
            try:
                drive_file = manager.upload_and_share(
                    file_path=path,
                    folder_id=folder_id,
                    mime_type=mime_type,
                    share_public=share_public
                )
                drive_urls[key] = {
                    "file_id": drive_file.file_id,
                    "web_view_link": drive_file.web_view_link,
                    "web_content_link": drive_file.web_content_link,
                }
            except Exception as e:
                logger.warning(f"Drive upload failed for {key}: {e}")
                drive_urls[key] = {"error": str(e)}

        res["drive_urls"] = drive_urls
        return {"success": True, "drive_urls": drive_urls}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Drive upload error: {e}")
        raise HTTPException(status_code=500, detail=f"アップロード失敗: {str(e)}")


@app.post("/api/drive/revoke")
async def drive_revoke() -> Dict[str, str]:
    """Googleドライブ認証を解除"""
    try:
        manager = _get_drive_manager()
        manager.revoke_authentication()
        return {"status": "ok", "message": "認証を解除しました"}
    except Exception as e:
        logger.error(f"Drive revoke failed: {e}")
        raise HTTPException(status_code=500, detail=f"解除失敗: {str(e)}")


@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus exposition endpoint for application metrics."""
    from fastapi.responses import Response
    from src.observability import metrics as obs

    body, content_type = obs.render()
    return Response(content=body, media_type=content_type)


@app.get("/api/observability/status")
async def observability_status() -> Dict[str, Any]:
    """Return whether the observability backend is active."""
    from src.observability import metrics as obs
    return {
        "enabled": obs.enabled,
        "backend": "prometheus_client" if obs.enabled else "noop",
    }






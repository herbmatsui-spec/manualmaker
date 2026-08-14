"""
FastAPI Web Server for Manual Processor
"""

import logging
from typing import Dict, Any
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config.config import Config

logger = logging.getLogger(__name__)

config = Config.get_instance()

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
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def serve_dashboard(request: Request):
    """Web UI ダッシュボード画面"""
    return templates.TemplateResponse("index.html", {"request": request})


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
        "supported_extensions": config.supported_extensions
    }


import uuid
from pathlib import Path
from fastapi import UploadFile, File, HTTPException

# アップロード済みファイルのメタデータキャッシュ
UPLOADED_FILES: Dict[str, Dict[str, Any]] = {}


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)) -> Dict[str, Any]:
    """PDF ファイルをアップロードして一元管理ディレクトリに保存"""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF ファイルのみアップロード可能です。")
    
    file_bytes = await file.read()
    size_mb = len(file_bytes) / (1024 * 1024)
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


from pydantic import BaseModel
from src.processor.processor import DocumentProcessor

# 処理結果のインメモリキャッシュ
PROCESSING_RESULTS: Dict[str, Dict[str, Any]] = {}


class ProcessOptions(BaseModel):
    compact_layout: bool = False
    use_emojis: bool = False


@app.post("/api/process/{file_id}")
async def process_pdf_api(file_id: str, options: ProcessOptions = ProcessOptions()) -> Dict[str, Any]:
    """アップロード済み PDF をパイプライン処理"""
    if file_id not in UPLOADED_FILES:
        raise HTTPException(status_code=404, detail="指定された file_id が存在しません。")
    
    file_info = UPLOADED_FILES[file_id]
    pdf_path = Path(file_info["path"])

    processor = DocumentProcessor(config)
    result = processor.process_pdf(
        pdf_path,
        compact_layout=options.compact_layout,
        use_emojis=options.use_emojis
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


from fastapi.responses import FileResponse


@app.get("/api/download/{file_id}/{file_type}")
async def download_file_api(file_id: str, file_type: str):
    """生成ファイルのダウンロード API (file_type: pdf, docx, audio, diagram)"""
    if file_id not in PROCESSING_RESULTS:
        raise HTTPException(status_code=404, detail="処理結果が見つかりません。")
    
    res = PROCESSING_RESULTS[file_id]
    outputs = res.get("output_files", {})
    target_path_str = outputs.get(file_type)

    if not target_path_str or not Path(target_path_str).exists():
        raise HTTPException(status_code=404, detail=f"指定されたファイル ({file_type}) が存在しません。")

    file_path = Path(target_path_str)
    media_types = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "audio": "audio/mpeg",
        "diagram": "image/png"
    }

    return FileResponse(
        path=file_path,
        media_type=media_types.get(file_type, "application/octet-stream"),
        filename=file_path.name
    )


from src.diagram_generator import DiagramGenerator


class MermaidRenderRequest(BaseModel):
    mermaid_code: str
    theme: str = "default"
    width: int = 800
    height: int = 600


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


class MermaidRegenerateRequest(BaseModel):
    current_code: str
    instruction: str


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

    diagram_path = Path(diagram_path_str)
    diagram_gen = DiagramGenerator(api_key=config.gemini_api_key)

    try:
        # 新しい Mermaid コードから PNG 画像を生成
        rendered_path = diagram_gen.render_to_image(
            mermaid_code=req.mermaid_code,
            output_path=diagram_path,
            theme=req.theme,
            width=req.width,
            height=req.height
        )
        outputs["diagram"] = str(rendered_path)
        res["mermaid_code"] = req.mermaid_code

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

        return {"success": True, "message": "フロー図の保存とドキュメント再生成が完了しました。"}
    except Exception as e:
        logger.error(f"Save & rebuild error: {e}")
        raise HTTPException(status_code=500, detail=f"再生成エラー: {str(e)}")








"""
Pages Functions API Handler - PDF Processing (Queue-based)
"""

import json
import uuid
from functions._middleware import (
    json_response, error_response, handle_options,
    validate_request, validate_file_id
)
from src.r2_storage import get_file_manager
from config.config import Config


async def on_request(request, env, ctx):
    """Main entry point for /api/process* routes"""
    path = request.url.path
    method = request.method
    
    if method == "OPTIONS":
        return await handle_options(request)
    
    if path.startswith("/api/process/") and method == "POST":
        file_id = path.split("/")[-1]
        # Validate file_id
        validation_result = validate_file_id({"file_id": file_id})
        if not validation_result.valid:
            return error_response("Invalid file_id format", 400, validation_result.errors)
        return await process_pdf(request, env, ctx, file_id)
    elif path.startswith("/api/results/") and method == "GET":
        file_id = path.split("/")[-1]
        validation_result = validate_file_id({"file_id": file_id})
        if not validation_result.valid:
            return error_response("Invalid file_id format", 400, validation_result.errors)
        return await get_result(request, env, ctx, file_id)
    
    return error_response("Not found", 404)


@validate_request(validate_process_request)
async def process_pdf(request, env, ctx, file_id: str):
    """Enqueue PDF processing job"""
    try:
        # Get validated options
        options = getattr(request, '_validated_data', {})
        
        # Validate file exists
        file_manager = get_file_manager(env.FILES)
        
        # Check if upload exists
        uploads = file_manager.r2.list_files(f"uploads/{file_id}/")
        if not uploads:
            return error_response("指定された file_id が存在しません。", 404)
        
        # Get the PDF key (first uploaded file)
        pdf_key = uploads[0]["key"]
        
        # Prepare queue message
        queue_message = {
            "file_id": file_id,
            "pdf_key": pdf_key,
            "options": {
                "compact_layout": options.get("compact_layout", False),
                "use_emojis": options.get("use_emojis", False),
                "prompt_layout": options.get("prompt_layout"),
                "prompt_strict_mode": options.get("prompt_strict_mode"),
                "prompt_has_diagrams": options.get("prompt_has_diagrams"),
                "prompt_low_quality_mode": options.get("prompt_low_quality_mode"),
                "base_url": options.get("base_url", "https://manual-processor.pages.dev")
            }
        }
        
        # Send to queue
        if hasattr(env, 'PDF_QUEUE'):
            await env.PDF_QUEUE.send(queue_message)
        else:
            # Fallback: process synchronously (for local dev)
            return error_response(
                "Queue not configured. Please bind PDF_QUEUE in wrangler.toml", 
                503
            )
        
        # Initialize progress tracking
        if hasattr(env, 'PROGRESS_DO'):
            try:
                stub_id = env.PROGRESS_DO.id_from_name(file_id)
                stub = env.PROGRESS_DO.get(stub_id)
                await stub.fetch(f"https://do/progress/{file_id}", method="POST", body=json.dumps({
                    "status": "queued",
                    "progress": 0,
                    "stage": "キューに追加されました"
                }))
            except Exception as e:
                print(f"Progress DO init error: {e}")
        
        return json_response({
            "success": True,
            "file_id": file_id,
            "status": "queued",
            "message": "処理がキューに追加されました。進捗は WebSocket で確認できます。"
        })
        
    except Exception as e:
        return error_response(f"処理開始エラー: {str(e)}", 500)


async def get_result(request, env, ctx, file_id: str):
    """Get processing result"""
    try:
        file_manager = get_file_manager(env.FILES)
        result = file_manager.get_result(file_id)
        
        if not result:
            return error_response("処理結果が見つかりません。", 404)
        
        return json_response(result)
        
    except Exception as e:
        return error_response(f"結果取得エラー: {str(e)}", 500)
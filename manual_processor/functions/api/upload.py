"""
Pages Functions API Handler - File Upload
"""

import uuid
import json
from functions._middleware import (
    json_response, error_response, handle_options,
    validate_file_id
)
from src.r2_storage import get_file_manager
from src.utils.validators import validate_pdf_content, validate_extension
from config.config import Config


MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB default


async def on_request(request, env, ctx):
    """Main entry point for /api/upload* routes"""
    path = request.url.path
    method = request.method
    
    if method == "OPTIONS":
        return await handle_options(request)
    
    if path == "/api/upload" and method == "POST":
        return await upload_file(request, env, ctx)
    elif path == "/api/uploads" and method == "GET":
        return await list_uploads(request, env, ctx)
    elif path.startswith("/api/upload/") and method == "DELETE":
        file_id = path.split("/")[-1]
        # Validate file_id
        validation_result = validate_file_id({"file_id": file_id})
        if not validation_result.valid:
            return error_response("Invalid file_id format", 400, validation_result.errors)
        return await delete_upload(request, env, ctx, file_id)
    
    return error_response("Not found", 404)


async def upload_file(request, env, ctx):
    """Upload PDF file to R2"""
    config = Config.get_instance()
    max_size_mb = getattr(config, 'web_upload_max_mb', 100)
    max_size_bytes = max_size_mb * 1024 * 1024
    
    try:
        # Parse multipart form data
        form_data = await request.formData()
        file = form_data.get("file")
        
        if not file:
            return error_response("ファイルが指定されていません。", 400)
        
        # Validate extension
        filename = file.name if hasattr(file, 'name') else "upload.pdf"
        if not validate_extension(filename, [".pdf"]):
            return error_response("PDF ファイルのみアップロード可能です。", 400)
        
        # Read file data
        file_data = await file.arrayBuffer()
        file_bytes = bytes(file_data)
        size_mb = len(file_bytes) / (1024 * 1024)
        
        # Validate PDF content
        if not validate_pdf_content(file_bytes):
            return error_response("ファイル内容がPDF形式ではありません。", 400)
        
        # Check size
        if size_mb > max_size_mb:
            return error_response(
                f"ファイルサイズ ({size_mb:.1f}MB) が上限 ({max_size_mb}MB) を超えています。",
                400
            )
        
        # Generate file ID and save to R2
        file_id = uuid.uuid4().hex
        file_manager = get_file_manager(env.FILES)
        
        result = file_manager.save_upload(file_id, filename, file_bytes)
        result.update({
            "file_id": file_id,
            "filename": filename,
            "size_mb": round(size_mb, 2)
        })
        
        return json_response(result)
        
    except Exception as e:
        return error_response(f"アップロードエラー: {str(e)}", 500)


async def list_uploads(request, env, ctx):
    """List uploaded files"""
    try:
        file_manager = get_file_manager(env.FILES)
        uploads = file_manager.list_uploads()
        return json_response({"uploads": uploads})
    except Exception as e:
        return error_response(f"一覧取得エラー: {str(e)}", 500)


async def delete_upload(request, env, ctx, file_id: str):
    """Delete uploaded file"""
    try:
        file_manager = get_file_manager(env.FILES)
        
        # Find and delete upload files
        uploads = file_manager.r2.list_files(f"uploads/{file_id}/")
        for upload in uploads:
            file_manager.r2.delete_file(upload["key"])
        
        # Also delete results if exist
        results = file_manager.r2.list_files(f"results/{file_id}/")
        for result in results:
            file_manager.r2.delete_file(result["key"])
        
        return json_response({"success": True, "file_id": file_id})
    except Exception as e:
        return error_response(f"削除エラー: {str(e)}", 500)
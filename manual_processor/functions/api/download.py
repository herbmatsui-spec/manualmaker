"""
Pages Functions API Handler - File Download
"""

import json
import zipfile
import io
from typing import Dict
from functions._middleware import (
    json_response, error_response, handle_options,
    validate_file_id, validate_file_type, cors_headers
)
from src.r2_storage import get_file_manager
from config.config import Config


async def on_request(request, env, ctx):
    """Main entry point for /api/download* routes"""
    path = request.url.path
    method = request.method
    
    if method == "OPTIONS":
        return await handle_options(request)
    
    if path.startswith("/api/download/") and method == "GET":
        # Parse: /api/download/{file_id}/{file_type}
        parts = path.split("/")
        if len(parts) >= 5:
            file_id = parts[3]
            file_type = parts[4]
            
            # Validate parameters
            file_id_validation = validate_file_id({"file_id": file_id})
            if not file_id_validation.valid:
                return error_response("Invalid file_id format", 400, file_id_validation.errors)
            
            file_type_validation = validate_file_type({"file_type": file_type})
            if not file_type_validation.valid:
                return error_response("Invalid file_type", 400, file_type_validation.errors)
            
            return await download_file(request, env, ctx, file_id, file_type)
    
    return error_response("Not found", 404)


async def download_file(request, env, ctx, file_id: str, file_type: str):
    """Download generated file"""
    try:
        file_manager = get_file_manager(env.FILES)
        result = file_manager.get_result(file_id)
        
        if not result:
            return error_response("処理結果が見つかりません。", 404)
        
        outputs = result.get("output_files", {})
        
        # Handle "all" - create zip
        if file_type == "all":
            return await create_zip_download(file_manager, file_id, outputs)
        
        # Get target file path
        target_key = None
        if file_type in outputs and outputs[file_type]:
            # Find the file in R2
            results = file_manager.r2.list_files(f"results/{file_id}/{file_type}/")
            if results:
                target_key = results[0]["key"]
        
        # Fallback for diagram
        if not target_key and file_type == "diagram":
            results = file_manager.r2.list_files(f"results/{file_id}/diagram_markdown/")
            if results:
                target_key = results[0]["key"]
        
        if not target_key:
            return error_response(f"指定されたファイル ({file_type}) が存在しません。", 404)
        
        # Download from R2
        file_data = file_manager.r2.download_file(target_key)
        
        # Determine media type
        media_types = {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "audio": "audio/mpeg",
            "diagram": "text/markdown",
            "diagram_markdown": "text/markdown",
            "diagram_mermaid": "text/plain",
            "qr": "image/png"
        }
        
        # Extract filename from key
        filename = target_key.split("/")[-1]
        
        return {
            "status": 200,
            "headers": {
                "Content-Type": media_types.get(file_type, "application/octet-stream"),
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(file_data)),
                **cors_headers()
            },
            "body": file_data
        }
        
    except Exception as e:
        return error_response(f"ダウンロードエラー: {str(e)}", 500)


async def create_zip_download(file_manager, file_id: str, outputs: Dict[str, str]):
    """Create zip archive of all output files"""
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for output_type, _ in outputs.items():
            if not _:
                continue
            results = file_manager.r2.list_files(f"results/{file_id}/{output_type}/")
            for result in results:
                file_data = file_manager.r2.download_file(result["key"])
                zipf.writestr(result["key"].split("/")[-1], file_data)
    
    zip_buffer.seek(0)
    zip_data = zip_buffer.read()
    
    return {
        "status": 200,
        "headers": {
            "Content-Type": "application/zip",
            "Content-Disposition": f'attachment; filename="{file_id}_outputs.zip"',
            "Content-Length": str(len(zip_data)),
            **cors_headers()
        },
        "body": zip_data
    }
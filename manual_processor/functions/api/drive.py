"""
Pages Functions API Handler - Google Drive Integration
"""

import json
from functions._middleware import (
    json_response, error_response, handle_options,
    validate_request, validate_file_id,
    validate_drive_upload_request
)
from config.config import Config
from src.google_drive_manager import GoogleDriveManager, GoogleDriveError
from pathlib import Path
from src.r2_storage import get_file_manager


def _get_drive_manager(config) -> GoogleDriveManager:
    """Create GoogleDriveManager from config"""
    credentials_path = getattr(config.drive, 'credentials_path', None)
    if credentials_path:
        creds_path = Path(credentials_path)
    else:
        creds_path = Path(__file__).parent.parent.parent / "credentials.json"
    return GoogleDriveManager(credentials_path=creds_path)


async def on_request(request, env, ctx):
    """Main entry point for /api/drive* routes"""
    path = request.url.path
    method = request.method
    
    if method == "OPTIONS":
        return await handle_options(request)
    
    config = Config.get_instance()
    
    if path == "/api/drive/status" and method == "GET":
        return await drive_status(request, env, ctx, config)
    elif path == "/api/drive/auth" and method == "GET":
        return await drive_auth(request, env, ctx, config)
    elif path == "/api/drive/callback" and method == "GET":
        return await drive_callback(request, env, ctx, config)
    elif path.startswith("/api/drive/upload/") and method == "POST":
        file_id = path.split("/")[-1]
        # Validate file_id
        validation_result = validate_file_id({"file_id": file_id})
        if not validation_result.valid:
            return error_response("Invalid file_id format", 400, validation_result.errors)
        return await drive_upload(request, env, ctx, config, file_id)
    elif path == "/api/drive/revoke" and method == "POST":
        return await drive_revoke(request, env, ctx, config)
    
    return error_response("Not found", 404)


async def drive_status(request, env, ctx, config):
    """Get Google Drive auth status"""
    try:
        manager = _get_drive_manager(config)
        return json_response({
            "authenticated": manager.is_authenticated(),
            "enabled": getattr(config.drive, 'enabled', False),
        })
    except Exception as e:
        return json_response({
            "authenticated": False,
            "enabled": False,
            "error": str(e)
        })


async def drive_auth(request, env, ctx, config):
    """Get Google OAuth2 auth URL"""
    try:
        manager = _get_drive_manager(config)
        # Use the Pages Functions URL for callback
        base_url = env.BASE_URL if hasattr(env, 'BASE_URL') else "https://manual-processor.pages.dev"
        redirect_uri = f"{base_url}/api/drive/callback"
        auth_url = manager.get_authorization_url(redirect_uri=redirect_uri)
        return json_response({"auth_url": auth_url})
    except GoogleDriveError as e:
        return error_response(str(e), 400)
    except Exception as e:
        return error_response(f"認証URL生成エラー: {str(e)}", 500)


async def drive_callback(request, env, ctx, config):
    """OAuth2 callback handler"""
    from functions._middleware import get_query_params
    params = get_query_params(request)
    code = params.get("code")
    
    if not code:
        return error_response("認証コードがありません", 400)
    
    try:
        manager = _get_drive_manager(config)
        base_url = env.BASE_URL if hasattr(env, 'BASE_URL') else "https://manual-processor.pages.dev"
        redirect_uri = f"{base_url}/api/drive/callback"
        token_info = manager.exchange_code(code, redirect_uri=redirect_uri)
        return json_response({"status": "ok", "message": "認証成功", "token_info": token_info})
    except GoogleDriveError as e:
        return error_response(str(e), 400)
    except Exception as e:
        return error_response(f"認証処理エラー: {str(e)}", 500)


@validate_request(validate_drive_upload_request)
async def drive_upload(request, env, ctx, config, file_id: str):
    """Upload processing results to Google Drive"""
    try:
        manager = _get_drive_manager(config)
        if not manager.is_authenticated():
            return error_response("Googleドライブに認証されていません。", 401)
        
        file_manager = get_file_manager(env.FILES)
        result = file_manager.get_result(file_id)
        
        if not result:
            return error_response("処理結果が見つかりません。", 404)
        
        outputs = result.get("output_files", {})
        drive_urls = {}
        
        # Get or create folder
        folder_id = getattr(config.drive, 'folder_id', None)
        if not folder_id and getattr(config.drive, 'folder_name', None):
            try:
                folder_id = manager.create_folder(config.drive.folder_name)
            except Exception as e:
                print(f"Failed to create Drive folder: {e}")
        
        share_public = getattr(config.drive, 'share_public', True)
        
        upload_map = {
            "pdf": ("application/pdf", outputs.get("pdf")),
            "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", outputs.get("docx")),
            "audio": ("audio/mpeg", outputs.get("audio")),
            "diagram": ("image/png", outputs.get("diagram")),
            "qr": ("image/png", outputs.get("qr")),
        }
        
        for key, (mime_type, r2_path) in upload_map.items():
            if not r2_path:
                continue
            
            try:
                # Download from R2
                file_data = file_manager.r2.download_file(r2_path)
                
                # Upload to Drive
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=f'.{key}', delete=False) as tmp:
                    tmp.write(file_data)
                    tmp_path = Path(tmp.name)
                
                try:
                    drive_file = manager.upload_and_share(
                        file_path=tmp_path,
                        folder_id=folder_id,
                        mime_type=mime_type,
                        share_public=share_public
                    )
                    drive_urls[key] = {
                        "file_id": drive_file.file_id,
                        "web_view_link": drive_file.web_view_link,
                        "web_content_link": drive_file.web_content_link,
                    }
                finally:
                    try:
                        tmp_path.unlink()
                    except Exception:
                        pass
                        
            except Exception as e:
                print(f"Drive upload failed for {key}: {e}")
                drive_urls[key] = {"error": str(e)}
        
        # Save drive URLs to result
        result["drive_urls"] = drive_urls
        file_manager.save_json_result(file_id, result)
        
        return json_response({"success": True, "drive_urls": drive_urls})
        
    except Exception as e:
        return error_response(f"アップロード失敗: {str(e)}", 500)


async def drive_revoke(request, env, ctx, config):
    """Revoke Google Drive authentication"""
    try:
        manager = _get_drive_manager(config)
        manager.revoke_authentication()
        return json_response({"status": "ok", "message": "認証を解除しました"})
    except Exception as e:
        return error_response(f"解除失敗: {str(e)}", 500)
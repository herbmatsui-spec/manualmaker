"""
Pages Functions API Handler - Security
"""

import json
import os
from functions._middleware import (
    json_response, error_response, handle_options,
    validate_request, validate_query_params,
    validate_security_mask_request,
    validate_i18n_detect_request
)
from config.config import Config
from src.security_manager import SecurityManager, AuditLogger


async def on_request(request, env, ctx):
    """Main entry point for /api/security* routes"""
    path = request.url.path
    method = request.method
    
    if method == "OPTIONS":
        return await handle_options(request)
    
    if path == "/api/security/status" and method == "GET":
        return await get_security_status(request, env, ctx)
    elif path == "/api/security/audit" and method == "GET":
        return await get_audit_logs(request, env, ctx)
    elif path == "/api/security/mask" and method == "POST":
        return await mask_text(request, env, ctx)
    
    return error_response("Not found", 404)


async def get_security_status(request, env, ctx):
    """Get security configuration status"""
    config = Config.get_instance()
    
    return json_response({
        "pii_masking_enabled": getattr(config, "pii_masking_enabled", False),
        "encryption_available": True,
        "encryption_key_set": bool(os.getenv("ENCRYPTION_KEY")),
        "keyring_available": True,
        "audit_log_enabled": True
    })


@validate_query_params(
    optional={
        "limit": {"type": "int", "min": 1, "max": 1000}
    }
)
async def get_audit_logs(request, env, ctx):
    """Get audit logs"""
    try:
        params = getattr(request, '_query_params', {})
        limit = int(params.get("limit", "100"))
    except Exception:
        limit = 100
    
    try:
        audit = AuditLogger()
        logs = audit.get_recent_logs(limit=limit)
        return json_response({"logs": logs, "count": len(logs)})
    except Exception as e:
        return error_response(f"監査ログ取得エラー: {str(e)}", 500)


@validate_request(validate_security_mask_request)
async def mask_text(request, env, ctx):
    """Mask sensitive data in text"""
    try:
        # Use validated data
        data = getattr(request, '_validated_data', {})
        text = data.get("text", "")
        
        if not text:
            return json_response({"masked_text": "", "counts": {}})
        
        masked, info = SecurityManager.mask_sensitive_data(text, record_positions=True)
        return json_response({
            "masked_text": masked,
            "counts": info.get("counts", {}),
            "positions_count": len(info.get("positions", []))
        })
    except Exception as e:
        return error_response(f"マスキングエラー: {str(e)}", 500)
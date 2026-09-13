"""
Pages Functions Middleware - CORS, Auth, Rate Limiting, Validation, Error Handling
"""

import json
import time
from typing import Dict, Any, Optional, Callable
from functools import wraps


def cors_headers(origin: str = "*") -> Dict[str, str]:
    """Standard CORS headers"""
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With",
        "Access-Control-Expose-Headers": "Content-Disposition",
        "Access-Control-Max-Age": "600"
    }


def json_response(data: Any, status: int = 200, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Create JSON response with CORS headers"""
    response_headers = {
        "Content-Type": "application/json; charset=utf-8",
        **(cors_headers()),
        **(headers or {})
    }
    return {
        "status": status,
        "headers": response_headers,
        "body": json.dumps(data, ensure_ascii=False)
    }


def error_response(message: str, status: int = 400, details: Any = None) -> Dict[str, Any]:
    """Create error response"""
    data = {"error": message}
    if details:
        data["details"] = details
    return json_response(data, status)


# Simple in-memory rate limiter (for edge Workers, use KV)
_rate_limit_store: Dict[str, list] = {}


def rate_limit(max_requests: int = 100, window_seconds: int = 60):
    """Rate limiting decorator"""
    def decorator(handler: Callable) -> Callable:
        @wraps(handler)
        async def wrapper(request: Any, env: Any, ctx: Any) -> Any:
            # Get client identifier
            client_ip = request.headers.get("CF-Connecting-IP", "unknown")
            key = f"ratelimit:{client_ip}:{request.url.path}"
            
            now = time.time()
            if key not in _rate_limit_store:
                _rate_limit_store[key] = []
            
            # Clean old entries
            _rate_limit_store[key] = [
                ts for ts in _rate_limit_store[key] 
                if now - ts < window_seconds
            ]
            
            if len(_rate_limit_store[key]) >= max_requests:
                return error_response(
                    "Rate limit exceeded", 
                    429,
                    {"retry_after": window_seconds}
                )
            
            _rate_limit_store[key].append(now)
            
            return await handler(request, env, ctx)
        return wrapper
    return decorator


def require_auth(handler: Callable) -> Callable:
    """Authentication decorator (placeholder for future auth implementation)"""
    @wraps(handler)
    async def wrapper(request: Any, env: Any, ctx: Any) -> Any:
        # For now, just pass through
        # In production, validate JWT token or API key
        auth_header = request.headers.get("Authorization", "")
        if not auth_header and env.ENVIRONMENT == "production":
            # Allow unauthenticated for now
            pass
        return await handler(request, env, ctx)
    return wrapper


async def handle_options(request: Any) -> Dict[str, Any]:
    """Handle OPTIONS preflight requests"""
    return {
        "status": 204,
        "headers": cors_headers()
    }


async def parse_json_body(request: Any) -> Dict[str, Any]:
    """Parse JSON request body"""
    try:
        return await request.json()
    except Exception:
        return {}


def get_query_params(request: Any) -> Dict[str, str]:
    """Get query parameters from request"""
    url = request.url
    params = {}
    if "?" in url:
        query_string = url.split("?", 1)[1]
        for param in query_string.split("&"):
            if "=" in param:
                key, value = param.split("=", 1)
                params[key] = value
    return params


# Re-export validation functions
from functions._middleware.validation import (
    validate_request,
    validate_query_params,
    ValidationError,
    ValidationResult,
    validate_process_request,
    validate_mermaid_validate_request,
    validate_mermaid_render_request,
    validate_mermaid_regenerate_request,
    validate_mermaid_save_request,
    validate_drive_upload_request,
    validate_i18n_set_request,
    validate_i18n_detect_request,
    validate_security_mask_request,
    validate_file_id,
    validate_file_type,
)

# Re-export error handling functions
from functions._middleware.error_handling import (
    error_handler,
    create_request_context,
    log_request,
    log_structured,
    log_middleware,
)
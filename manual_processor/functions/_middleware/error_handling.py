"""
Error Handling and Logging Middleware for Pages Functions
"""

import json
import traceback
import logging
import time
import uuid
from typing import Dict, Any, Callable, Optional
from functools import wraps

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class RequestContext:
    """Context for tracking request information"""
    def __init__(self, request_id: str = None):
        self.request_id = request_id or str(uuid.uuid4())[:8]
        self.start_time = time.time()
        self.path = ""
        self.method = ""
        self.client_ip = ""
        self.user_agent = ""
    
    def elapsed_ms(self) -> float:
        return (time.time() - self.start_time) * 1000
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "path": self.path,
            "method": self.method,
            "client_ip": self.client_ip,
            "user_agent": self.user_agent,
            "elapsed_ms": round(self.elapsed_ms(), 2)
        }


def create_request_context(request: Any) -> RequestContext:
    """Create request context from request"""
    ctx = RequestContext()
    ctx.path = getattr(request.url, 'path', '')
    ctx.method = getattr(request, 'method', '')
    ctx.client_ip = request.headers.get("CF-Connecting-IP", "unknown")
    ctx.user_agent = request.headers.get("User-Agent", "unknown")
    return ctx


def log_request(ctx: RequestContext, level: str = "info"):
    """Log request information"""
    log_data = ctx.to_dict()
    if level == "info":
        logger.info(f"Request: {json.dumps(log_data, ensure_ascii=False)}")
    elif level == "error":
        logger.error(f"Request error: {json.dumps(log_data, ensure_ascii=False)}")


def error_handler(handler: Callable) -> Callable:
    """Decorator for consistent error handling"""
    @wraps(handler)
    async def wrapper(request, env, ctx):
        request_ctx = create_request_context(request)
        
        try:
            return await handler(request, env, ctx)
        except ValidationError as e:
            request_ctx.end_time = time.time()
            log_request(request_ctx, "error")
            return error_response(e.message, 400, {"field": e.field, "code": e.code})
        except FileNotFoundError as e:
            request_ctx.end_time = time.time()
            log_request(request_ctx, "error")
            return error_response(str(e), 404)
        except PermissionError as e:
            request_ctx.end_time = time.time()
            log_request(request_ctx, "error")
            return error_response(str(e), 403)
        except ValueError as e:
            request_ctx.end_time = time.time()
            log_request(request_ctx, "error")
            return error_response(str(e), 400)
        except Exception as e:
            request_ctx.end_time = time.time()
            log_request(request_ctx, "error")
            logger.exception(f"Unhandled error in {request_ctx.path}: {e}")
            
            # Don't expose internal errors in production
            env_str = getattr(env, 'ENVIRONMENT', 'development')
            if env_str == 'production':
                return error_response("Internal server error", 500)
            else:
                return error_response(f"Internal error: {str(e)}", 500, {
                    "traceback": traceback.format_exc(),
                    "request_id": request_ctx.request_id
                })
    return wrapper


class ValidationError(Exception):
    """Validation error with field info"""
    def __init__(self, message: str, field: str = None, code: str = "VALIDATION_ERROR"):
        self.message = message
        self.field = field
        self.code = code
        super().__init__(message)


# Re-export for compatibility
def cors_headers(origin: str = "*") -> Dict[str, str]:
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With",
        "Access-Control-Expose-Headers": "Content-Disposition",
        "Access-Control-Max-Age": "600"
    }


def json_response(data: Any, status: int = 200, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
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
    data = {"error": message}
    if details:
        data["details"] = details
    return json_response(data, status)


async def handle_options(request: Any) -> Dict[str, Any]:
    return {
        "status": 204,
        "headers": cors_headers()
    }


async def parse_json_body(request: Any) -> Dict[str, Any]:
    try:
        return await request.json()
    except Exception:
        return {}


def get_query_params(request: Any) -> Dict[str, str]:
    url = request.url
    params = {}
    if "?" in url:
        query_string = url.split("?", 1)[1]
        for param in query_string.split("&"):
            if "=" in param:
                key, value = param.split("=", 1)
                params[key] = value
    return params


# Structured logging for Cloudflare
def log_structured(level: str, message: str, **kwargs):
    """Log structured data for Cloudflare Logs"""
    log_entry = {
        "timestamp": time.time(),
        "level": level.upper(),
        "message": message,
        **kwargs
    }
    if level == "error":
        logger.error(json.dumps(log_entry, ensure_ascii=False))
    elif level == "warning":
        logger.warning(json.dumps(log_entry, ensure_ascii=False))
    else:
        logger.info(json.dumps(log_entry, ensure_ascii=False))


# Request logging middleware
async def log_middleware(request: Any, env: Any, ctx: Any, handler: Callable) -> Any:
    """Middleware to log all requests"""
    request_ctx = create_request_context(request)
    
    # Log incoming request
    log_structured("info", "Incoming request", **request_ctx.to_dict())
    
    try:
        response = await handler(request, env, ctx)
        
        # Log response
        log_structured("info", "Response sent", 
            request_id=request_ctx.request_id,
            status=response.get("status", 0),
            elapsed_ms=request_ctx.elapsed_ms()
        )
        
        return response
    except Exception as e:
        log_structured("error", "Request failed",
            request_id=request_ctx.request_id,
            error=str(e),
            elapsed_ms=request_ctx.elapsed_ms()
        )
        raise
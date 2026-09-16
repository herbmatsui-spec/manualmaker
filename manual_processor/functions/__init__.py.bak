"""
Pages Functions Main Router
Routes requests to appropriate API handlers
"""

from functions._middleware import json_response, error_response, cors_headers
from functions.api.config import on_request as config_handler
from functions.api.upload import on_request as upload_handler
from functions.api.process import on_request as process_handler
from functions.api.download import on_request as download_handler
from functions.api.security import on_request as security_handler
from functions.api.ws_progress import on_request as ws_handler
from functions.api.mermaid import on_request as mermaid_handler
from functions.api.drive import on_request as drive_handler
from functions.api.observability import on_request as observability_handler
from functions.api.static import on_request as static_handler


# Route mapping
ROUTES = {
    "/api/health": config_handler,
    "/api/config": config_handler,
    "/api/i18n": config_handler,
    "/api/upload": upload_handler,
    "/api/uploads": upload_handler,
    "/api/process": process_handler,
    "/api/results": process_handler,
    "/api/download": download_handler,
    "/api/security": security_handler,
    "/ws/progress": ws_handler,
    "/api/mermaid": mermaid_handler,
    "/api/drive": drive_handler,
    "/metrics": observability_handler,
    "/api/observability": observability_handler,
    "/static": static_handler,  # Static files
}


async def on_request(request, env, ctx):
    """Main entry point for all requests"""
    path = request.url.path
    method = request.method
    
    # Handle CORS preflight
    if method == "OPTIONS":
        from functions._middleware import handle_options
        return await handle_options(request)
    
    # Root path -> serve index.html (dashboard)
    if path == "/" or path == "":
        return await static_handler(request, env, ctx)
    
    # Find matching route
    for route_path, handler in ROUTES.items():
        if path.startswith(route_path):
            return await handler(request, env, ctx)
    
    # API info endpoint
    if path == "/api":
        return json_response({
            "name": "手書きマニュアル処理システム API",
            "version": "3.1.0",
            "description": "Cloudflare Pages Functions API",
            "endpoints": {
                "health": "/api/health",
                "config": "/api/config",
                "upload": "/api/upload",
                "process": "/api/process/{file_id}",
                "results": "/api/results/{file_id}",
                "download": "/api/download/{file_id}/{type}",
                "websocket": "/ws/progress/{file_id}",
                "mermaid": "/api/mermaid/*",
                "drive": "/api/drive/*",
                "metrics": "/metrics"
            }
        })
    
    return error_response("Not found", 404)


# For Pages Functions - this is the main export
export = {
    "on_request": on_request
}
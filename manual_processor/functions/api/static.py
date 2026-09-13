"""
Pages Functions Static File Handler
Serves static assets and the main HTML template
"""

import mimetypes
from pathlib import Path
from functions._middleware import error_response

# Static files directory
STATIC_DIR = Path(__file__).parent.parent / "static"
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

# MIME type mapping
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("image/png", ".png")
mimetypes.add_type("image/jpeg", ".jpg")
mimetypes.add_type("font/woff2", ".woff2")


async def on_request(request, env, ctx):
    """Serve static files and index.html"""
    path = request.url.path
    
    # Root path -> serve index.html
    if path == "/" or path == "":
        return await serve_index(request, env, ctx)
    
    # Static files
    if path.startswith("/static/"):
        return await serve_static(request, env, ctx, path[8:])  # Remove "/static/"
    
    return error_response("Not found", 404)


async def serve_index(request, env, ctx):
    """Serve the main HTML template"""
    try:
        index_path = TEMPLATES_DIR / "index.html"
        if not index_path.exists():
            return error_response("Template not found", 404)
        
        content = index_path.read_text(encoding="utf-8")
        
        return {
            "status": 200,
            "headers": {
                "Content-Type": "text/html; charset=utf-8",
                "Cache-Control": "public, max-age=3600"
            },
            "body": content
        }
    except Exception as e:
        return error_response(f"Template error: {str(e)}", 500)


async def serve_static(request, env, ctx, file_path: str):
    """Serve static files with proper MIME types"""
    try:
        # Security: prevent directory traversal
        if ".." in file_path or file_path.startswith("/"):
            return error_response("Invalid path", 400)
        
        full_path = STATIC_DIR / file_path
        
        # Resolve and verify it's within STATIC_DIR
        try:
            full_path.resolve().relative_to(STATIC_DIR.resolve())
        except ValueError:
            return error_response("Invalid path", 400)
        
        if not full_path.exists() or not full_path.is_file():
            return error_response("File not found", 404)
        
        # Read file
        content = full_path.read_bytes()
        
        # Determine MIME type
        mime_type, _ = mimetypes.guess_type(str(full_path))
        if not mime_type:
            mime_type = "application/octet-stream"
        
        # Cache control based on file type
        if file_path.endswith((".css", ".js")):
            cache_control = "public, max-age=86400"  # 1 day
        elif file_path.endswith((".png", ".jpg", ".svg", ".woff2")):
            cache_control = "public, max-age=604800"  # 1 week
        else:
            cache_control = "public, max-age=3600"  # 1 hour
        
        return {
            "status": 200,
            "headers": {
                "Content-Type": mime_type,
                "Content-Length": str(len(content)),
                "Cache-Control": cache_control
            },
            "body": content
        }
        
    except Exception as e:
        return error_response(f"Static file error: {str(e)}", 500)
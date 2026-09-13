"""
Pages Functions API Handler - WebSocket Progress
"""

import json
from functions._middleware import json_response, error_response


async def on_request(request, env, ctx):
    """Main entry point for /ws/progress* routes"""
    path = request.url.path
    method = request.method
    
    # WebSocket upgrade
    if method == "GET" and request.headers.get("Upgrade", "").lower() == "websocket":
        return await handle_websocket(request, env, ctx)
    
    return error_response("WebSocket upgrade required", 426)


async def handle_websocket(request, env, ctx):
    """Handle WebSocket connection for progress updates"""
    # Extract file_id from path
    path = request.url.path
    parts = path.strip('/').split('/')
    if len(parts) < 3 or parts[0] != "ws" or parts[1] != "progress":
        return error_response("Invalid WebSocket path", 400)
    
    file_id = parts[2]
    
    # Check if Durable Object is available
    if not hasattr(env, 'PROGRESS_DO'):
        return error_response("Progress tracking not configured", 503)
    
    try:
        # Connect to Durable Object
        stub_id = env.PROGRESS_DO.id_from_name(file_id)
        stub = env.PROGRESS_DO.get(stub_id)
        
        # Forward WebSocket to Durable Object
        # This uses the WebSocket Hibernation API
        return await stub.fetch(request)
        
    except Exception as e:
        return error_response(f"WebSocket error: {str(e)}", 500)


# Alternative: Simple WebSocket handler without Durable Objects
# (for simpler deployments)
class SimpleProgressWebSocket:
    """Simple in-memory WebSocket progress handler"""
    
    def __init__(self):
        self.connections: dict = {}  # file_id -> set of websockets
    
    async def handle(self, request, env, ctx):
        """Handle WebSocket connection"""
        # This is a placeholder - actual implementation would use
        # the WebSocket API from the Pages Functions runtime
        pass


# For local development without Durable Objects
async def local_websocket_handler(request, env, ctx):
    """Local WebSocket handler for development"""
    from functions._middleware import cors_headers
    
    # Return upgrade response for local testing
    return {
        "status": 101,
        "headers": {
            "Upgrade": "websocket",
            "Connection": "Upgrade",
            **cors_headers()
        },
        "body": ""
    }
"""
Pages Functions API Handler - WebSocket Progress with Authentication
"""

import json
import base64
import time
from functions._middleware import json_response, error_response
from src.r2_storage import get_file_manager
from config.config import Config


def validate_jwt_token(token: str, secret: str) -> dict:
    """Validate JWT token (simplified version for Pages Functions)"""
    try:
        # Decode the token
        parts = token.split('.')
        if len(parts) != 3:
            return None
        
        # Decode payload
        payload_b64 = parts[1]
        # Add padding if needed
        payload_b64 += '=' * (4 - len(payload_b64) % 4)
        payload_json = base64.urlsafe_b64decode(payload_b64)
        payload = json.loads(payload_json)
        
        # Check expiration
        if 'exp' in payload and payload['exp'] < int(time.time()):
            return None
            
        return payload
    except Exception:
        return None


async def on_request(request, env, ctx):
    """Main entry point for /ws/progress* routes"""
    path = request.url.path
    method = request.method
    
    # WebSocket upgrade
    if method == "GET" and request.headers.get("Upgrade", "").lower() == "websocket":
        return await handle_websocket(request, env, ctx)
    
    return error_response("WebSocket upgrade required", 426)


async def handle_websocket(request, env, ctx):
    """Handle WebSocket connection for progress updates with authentication"""
    # Extract file_id from path
    path = request.url.path
    parts = path.strip('/').split('/')
    if len(parts) < 3 or parts[0] != "ws" or parts[1] != "progress":
        return error_response("Invalid WebSocket path", 400)
    
    file_id = parts[2]
    
    # Extract token from query parameters or headers
    token = None
    
    # Check query parameters first
    from functions._middleware import get_query_params
    params = get_query_params(request)
    token = params.get('token')
    
    # Check Sec-WebSocket-Protocol header as alternative
    if not token:
        protocol_header = request.headers.get('Sec-WebSocket-Protocol', '')
        if protocol_header:
            # Format could be "token,..." or just "token"
            protocols = [p.strip() for p in protocol_header.split(',')]
            # Look for a token-like string (long enough to be a JWT)
            for protocol in protocols:
                if len(protocol) > 10 and '.' in protocol:  # Basic JWT check for JWT-like
                    token = protocol
                    break
    
    # Validate token if we're in production
    config = Config.get_instance()
    if config.environment == "production":
        if not token:
            return error_response("WebSocket authentication required", 401)
        
        # Validate the token
        payload = validate_jwt_token(token, config.jwt_secret)
        if not payload:
            return error_response("Invalid or expired token", 401)
    
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
"""
Cloudflare Durable Object for WebSocket progress tracking
"""

import json
import logging
from typing import Dict, Set, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class ProgressState:
    """Progress state for a file processing job"""
    file_id: str
    status: str = "pending"  # pending, processing, completed, error
    progress: float = 0.0
    stage: str = "待機中"
    result: Optional[Dict] = None
    error: Optional[str] = None
    websockets: Set[str] = None  # Store WebSocket IDs
    
    def __post_init__(self):
        if self.websockets is None:
            self.websockets = set()
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data["websockets"] = list(self.websockets)
        return data


class ProgressDurableObject:
    """Durable Object for managing WebSocket connections and progress state"""
    
    def __init__(self, state: Any, env: Any):
        self.state = state
        self.env = env
        self.sessions: Dict[str, ProgressState] = {}
    
    async def fetch(self, request: Any) -> Any:
        """Handle HTTP requests to the Durable Object"""
        url = request.url
        method = request.method
        
        # Extract file_id from URL path
        path_parts = url.path.strip('/').split('/')
        if len(path_parts) < 2 or path_parts[0] != "progress":
            return self._json_response({"error": "Invalid path"}, 400)
        
        file_id = path_parts[1]
        
        if method == "GET":
            return await self._handle_get(file_id)
        elif method == "POST":
            return await self._handle_post(file_id, request)
        elif method == "DELETE":
            return await self._handle_delete(file_id)
        else:
            return self._json_response({"error": "Method not allowed"}, 405)
    
    async def _handle_get(self, file_id: str) -> Any:
        """Get progress state"""
        state = self.sessions.get(file_id)
        if not state:
            # Try to load from storage
            stored = await self.state.storage.get(f"progress:{file_id}")
            if stored:
                state = ProgressState(**stored)
                self.sessions[file_id] = state
        
        if not state:
            return self._json_response({"error": "Not found"}, 404)
        
        return self._json_response(state.to_dict())
    
    async def _handle_post(self, file_id: str, request: Any) -> Any:
        """Update progress state"""
        try:
            data = await request.json()
        except Exception:
            return self._json_response({"error": "Invalid JSON"}, 400)
        
        state = self.sessions.get(file_id)
        if not state:
            state = ProgressState(file_id=file_id)
            self.sessions[file_id] = state
        
        # Update state
        if "status" in data:
            state.status = data["status"]
        if "progress" in data:
            state.progress = float(data["progress"])
        if "stage" in data:
            state.stage = data["stage"]
        if "result" in data:
            state.result = data["result"]
        if "error" in data:
            state.error = data["error"]
        
        # Persist to storage
        await self.state.storage.put(f"progress:{file_id}", state.to_dict())
        
        # Broadcast to connected WebSockets
        await self._broadcast(file_id, state.to_dict())
        
        return self._json_response({"success": True})
    
    async def _handle_delete(self, file_id: str) -> Any:
        """Delete progress state"""
        if file_id in self.sessions:
            del self.sessions[file_id]
        await self.state.storage.delete(f"progress:{file_id}")
        return self._json_response({"success": True})
    
    async def _broadcast(self, file_id: str, data: Dict) -> None:
        """Broadcast progress update to all connected WebSockets"""
        state = self.sessions.get(file_id)
        if not state:
            return
        
        # In a real implementation, we'd iterate over WebSocket connections
        # and send the update. For now, we'll just log it.
        logger.info(f"Broadcasting progress for {file_id}: {data['progress']}% - {data['stage']}")
    
    def _json_response(self, data: Dict, status: int = 200) -> Any:
        """Create JSON response"""
        return {
            "status": status,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(data, ensure_ascii=False)
        }


# WebSocket handler for Pages Functions
class ProgressWebSocket:
    """WebSocket handler for real-time progress updates"""
    
    def __init__(self, env: Any):
        self.env = env
    
    async def handle_websocket(self, request: Any, file_id: str) -> Any:
        """Handle WebSocket connection for progress updates"""
        # Upgrade to WebSocket
        ws_pair = request.env.PROGRESS_DO.fetch(
            f"https://do/websocket/{file_id}",
            method="GET",
            headers={"Upgrade": "websocket"}
        )
        
        # This is a simplified version - actual implementation would
        # use the WebSocket Hibernation API
        return ws_pair


# Export for Pages Functions
export = {
    "ProgressDurableObject": ProgressDurableObject
}
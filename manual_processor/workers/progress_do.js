/**
 * Cloudflare Durable Object for WebSocket Progress Tracking
 * This runs in the Workers runtime
 */

export class ProgressDurableObject {
  constructor(state, env) {
    this.state = state;
    this.env = env;
    this.sessions = new Map(); // file_id -> { websockets: Set, state: ProgressState }
  }

  async fetch(request) {
    const url = new URL(request.url);
    const path = url.pathname;
    const method = request.method;

    // Extract file_id from path
    const pathParts = path.split('/').filter(Boolean);
    if (pathParts[0] !== 'progress' || pathParts.length < 2) {
      return new Response(JSON.stringify({ error: 'Invalid path' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    const fileId = pathParts[1];

    if (method === 'GET') {
      return this.handleGet(fileId);
    } else if (method === 'POST') {
      return this.handlePost(fileId, request);
    } else if (method === 'DELETE') {
      return this.handleDelete(fileId);
    } else if (method === 'GET' && request.headers.get('Upgrade') === 'websocket') {
      return this.handleWebSocket(fileId, request);
    }

    return new Response(JSON.stringify({ error: 'Method not allowed' }), {
      status: 405,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  async handleGet(fileId) {
    // Try to get from storage
    const stored = await this.state.storage.get(`progress:${fileId}`);
    if (!stored) {
      return new Response(JSON.stringify({ error: 'Not found' }), {
        status: 404,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    return new Response(JSON.stringify(stored), {
      headers: { 'Content-Type': 'application/json' }
    });
  }

  async handlePost(fileId, request) {
    let data;
    try {
      data = await request.json();
    } catch {
      return new Response(JSON.stringify({ error: 'Invalid JSON' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    // Get or create state
    let state = await this.state.storage.get(`progress:${fileId}`);
    if (!state) {
      state = {
        file_id: fileId,
        status: 'pending',
        progress: 0,
        stage: '待機中',
        result: null,
        error: null
      };
    }

    // Update state
    if (data.status) state.status = data.status;
    if (data.progress !== undefined) state.progress = data.progress;
    if (data.stage) state.stage = data.stage;
    if (data.result) state.result = data.result;
    if (data.error) state.error = data.error;

    // Persist
    await this.state.storage.put(`progress:${fileId}`, state);

    // Broadcast to WebSockets
    await this.broadcast(fileId, state);

    return new Response(JSON.stringify({ success: true }), {
      headers: { 'Content-Type': 'application/json' }
    });
  }

  async handleDelete(fileId) {
    await this.state.storage.delete(`progress:${fileId}`);
    const session = this.sessions.get(fileId);
    if (session) {
      // Close all WebSockets
      for (const ws of session.websockets) {
        ws.close();
      }
      this.sessions.delete(fileId);
    }
    return new Response(JSON.stringify({ success: true }), {
      headers: { 'Content-Type': 'application/json' }
    });
  }

  async handleWebSocket(fileId, request) {
    // Upgrade to WebSocket
    const webSocketPair = new WebSocketPair();
    const [client, server] = Object.values(webSocketPair);

    // Accept the WebSocket
    server.accept();

    // Get or create session
    let session = this.sessions.get(fileId);
    if (!session) {
      session = { websockets: new Set(), state: null };
      this.sessions.set(fileId, session);
    }

    session.websockets.add(server);

    // Send current state if available
    const stored = await this.state.storage.get(`progress:${fileId}`);
    if (stored) {
      server.send(JSON.stringify(stored));
    }

    // Handle incoming messages (ping/pong)
    server.addEventListener('message', async (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'ping') {
          server.send(JSON.stringify({ type: 'pong' }));
        }
      } catch {
        // Ignore invalid messages
      }
    });

    // Handle close
    server.addEventListener('close', () => {
      session.websockets.delete(server);
      if (session.websockets.size === 0) {
        this.sessions.delete(fileId);
      }
    });

    // Handle errors
    server.addEventListener('error', () => {
      session.websockets.delete(server);
    });

    return new Response(null, {
      status: 101,
      webSocket: client
    });
  }

  async broadcast(fileId, state) {
    const session = this.sessions.get(fileId);
    if (!session) return;

    const message = JSON.stringify(state);
    for (const ws of session.websockets) {
      try {
        ws.send(message);
      } catch {
        // Remove broken connections
        session.websockets.delete(ws);
      }
    }
  }
}
"""
Pages Functions API Handler - Observability/Metrics
"""

import json
from functions._middleware import json_response, error_response


async def on_request(request, env, ctx):
    """Main entry point for /metrics and /api/observability* routes"""
    path = request.url.path
    method = request.method
    
    if method == "OPTIONS":
        from functions._middleware import handle_options
        return await handle_options(request)
    
    if path == "/metrics" and method == "GET":
        return await prometheus_metrics(request, env, ctx)
    elif path == "/api/observability/status" and method == "GET":
        return await observability_status(request, env, ctx)
    
    return error_response("Not found", 404)


async def prometheus_metrics(request, env, ctx):
    """Prometheus metrics endpoint"""
    try:
        from src.observability import metrics as obs
        
        body, content_type = obs.render()
        
        return {
            "status": 200,
            "headers": {
                "Content-Type": content_type,
                **cors_headers()
            },
            "body": body
        }
    except Exception as e:
        return error_response(f"メトリクスエラー: {str(e)}", 500)


async def observability_status(request, env, ctx):
    """Observability backend status"""
    try:
        from src.observability import metrics as obs
        return json_response({
            "enabled": obs.enabled,
            "backend": "prometheus_client" if obs.enabled else "noop",
        })
    except Exception as e:
        return error_response(f"ステータス取得エラー: {str(e)}", 500)


def cors_headers():
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    }
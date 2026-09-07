"""
Security headers middleware for FastAPI.
Adds common security headers to all responses.
"""

import logging
from typing import List, Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds security headers to all responses.
    
    Headers added:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - Strict-Transport-Security: max-age=31536000
    - Content-Security-Policy: default-src 'self'
    - X-XSS-Protection: 1; mode=block
    - Referrer-Policy: strict-origin-when-cross-origin
    """

    def __init__(
        self,
        app,
        allowed_hosts: Optional[List[str]] = None,
        enable_hsts: bool = True,
        enable_csp: bool = True,
    ):
        super().__init__(app)
        self.allowed_hosts = allowed_hosts or ["localhost", "127.0.0.1"]
        self.enable_hsts = enable_hsts
        self.enable_csp = enable_csp

    async def dispatch(self, request: Request, call_next):
        # Check host header
        host = request.headers.get("host", "").split(":")[0]
        if self.allowed_hosts and host not in self.allowed_hosts:
            logger.warning(f"Invalid Host header: {host}")
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Invalid Host header")

        # Process request
        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # HSTS (only for HTTPS)
        if self.enable_hsts and request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # CSP
        if self.enable_csp:
            csp_policy = self._build_csp_policy(request)
            response.headers["Content-Security-Policy"] = csp_policy

        return response

    def _build_csp_policy(self, request: Request) -> str:
        """Build Content Security Policy based on request"""
        # Basic policy - can be extended
        directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline'",  # For inline scripts in development
            "style-src 'self' 'unsafe-inline'",   # For inline styles
            "img-src 'self' data: https:",
            "font-src 'self' data:",
            "connect-src 'self'",
            "frame-ancestors 'none'",
        ]
        
        # In production, remove unsafe-inline
        if request.url.scheme == "https":
            directives = [
                "default-src 'self'",
                "script-src 'self'",
                "style-src 'self'",
                "img-src 'self' data: https:",
                "font-src 'self' data:",
                "connect-src 'self'",
                "frame-ancestors 'none'",
            ]
        
        return "; ".join(directives)

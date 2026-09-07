"""
Rate limiting middleware for FastAPI.
Implements sliding window rate limiting per IP address.
"""

import time
import logging
from typing import Dict, Tuple
from collections import defaultdict
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding window rate limiting middleware.
    
    Limits requests per IP address within a time window.
    """

    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        window_seconds: int = 60,
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.window_seconds = window_seconds
        self._requests: Dict[str, list] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        client_ip = self._get_client_ip(request)
        
        # Skip rate limiting for localhost in development
        if client_ip in ("127.0.0.1", "::1", "localhost"):
            return await call_next(request)

        # Check rate limit
        allowed, remaining, reset_time = self._check_rate_limit(client_ip)
        
        if not allowed:
            logger.warning(
                f"Rate limit exceeded for {client_ip}: "
                f"{self.requests_per_minute} requests/{self.window_seconds}s"
            )
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please try again later.",
                headers={
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_time),
                }
            )

        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)
        
        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request"""
        # Check X-Forwarded-For header (for proxies)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct client
        return request.client.host if request.client else "unknown"

    def _check_rate_limit(self, client_ip: str) -> Tuple[bool, int, int]:
        """
        Check if request is within rate limit.
        
        Returns:
            (allowed, remaining_requests, reset_timestamp)
        """
        now = time.time()
        window_start = now - self.window_seconds
        
        # Clean old requests outside window
        self._requests[client_ip] = [
            req_time for req_time in self._requests[client_ip]
            if req_time > window_start
        ]
        
        current_count = len(self._requests[client_ip])
        
        if current_count >= self.requests_per_minute:
            # Rate limit exceeded
            oldest_request = min(self._requests[client_ip])
            reset_time = int(oldest_request + self.window_seconds)
            return False, 0, reset_time
        
        # Add current request
        self._requests[client_ip].append(now)
        remaining = self.requests_per_minute - current_count - 1
        reset_time = int(now + self.window_seconds)
        
        return True, remaining, reset_time

    def reset(self, client_ip: str = None) -> None:
        """
        Reset rate limit counters.
        
        Args:
            client_ip: Specific IP to reset, or None to reset all
        """
        if client_ip:
            self._requests.pop(client_ip, None)
        else:
            self._requests.clear()

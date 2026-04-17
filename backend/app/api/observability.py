from __future__ import annotations

import functools
import json
import time
from typing import Any, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import Message


def track_tables(*tables: str):
    """Decorator to mark which DB tables an endpoint interacts with."""

    def decorator(func: Callable):
        # We store the metadata on the function itself
        # FastAPI's Depends and other machinery might wrap this,
        # but we'll try to find it by unwrapping.
        if not hasattr(func, "_tracked_tables"):
            func._tracked_tables = []
        func._tracked_tables.extend(tables)

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        return wrapper

    return decorator


class ApiObservabilityMiddleware(BaseHTTPMiddleware):
    """Middleware to generate cURL commands and inject table metadata into responses."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start_time = time.monotonic()

        # Generate cURL command
        body = b""
        if request.method in ("POST", "PUT", "PATCH"):
            async def receive() -> Message:
                nonlocal body
                message = await request.receive()
                if message["type"] == "http.request":
                    body += message.get("body", b"")
                return message
            request._receive = receive

        curl_command = self._generate_curl_sync(request, body)

        # Call the actual endpoint
        response = await call_next(request)

        # Calculate duration
        duration = time.monotonic() - start_time

        # Extract tracked tables from the endpoint
        tracked_tables = []
        # Look for the endpoint in the scope
        endpoint = request.scope.get("endpoint")
        if endpoint:
            actual_func = endpoint
            # Unwrap functools.wraps
            while hasattr(actual_func, "__wrapped__"):
                actual_func = actual_func.__wrapped__
            
            tracked_tables = getattr(actual_func, "_tracked_tables", [])

        # Inject headers
        response.headers["X-Curl"] = curl_command
        response.headers["X-Tables"] = ",".join(tracked_tables)
        response.headers["X-Response-Time-Ms"] = f"{duration * 1000:.2f}"

        return response

    def _generate_curl_sync(self, request: Request, body: bytes) -> str:
        """Construct a cURL command from the request."""
        method = request.method
        url = str(request.url)
        headers = [f"-H '{k}: {v}'" for k, v in request.headers.items() if k.lower() not in ("content-length", "host")]
        
        curl = f"curl -X {method} '{url}'"
        if headers:
            curl += " " + " ".join(headers)

        if body:
            try:
                json_body = json.loads(body)
                curl += f" -d '{json.dumps(json_body)}'"
            except json.JSONDecodeError:
                # Escape single quotes for shell safety
                safe_body = body.decode('utf-8', errors='replace').replace("'", "'\\''")
                curl += f" -d '{safe_body}'"

        return curl

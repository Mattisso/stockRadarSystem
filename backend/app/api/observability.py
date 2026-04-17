from __future__ import annotations

import functools
import inspect
import json
import time
from typing import Any, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint


def track_tables(*tables: str):
    """Decorator to mark which DB tables an endpoint interacts with."""

    def decorator(func: Callable):
        # Store metadata on the function itself
        if not hasattr(func, "_tracked_tables"):
            func._tracked_tables = []
        func._tracked_tables.extend(tables)

        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await func(*args, **kwargs)

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return sync_wrapper

    return decorator


class ApiObservabilityMiddleware(BaseHTTPMiddleware):
    """Middleware to generate cURL commands and inject table metadata into responses."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start_time = time.monotonic()

        # Generate cURL command
        # Note: Capture body only if it's small and it's a mutation request
        # To avoid BaseHTTPMiddleware recursion/hang issues, we use a simpler approach
        body_to_log = b""
        if request.method in ("POST", "PUT", "PATCH"):
            # Peeking at the body in BaseHTTPMiddleware is notoriously difficult.
            # We'll skip body for now to prioritize stability and fix the 400 errors.
            body_to_log = b"[body capture disabled for stability]"

        curl_command = self._generate_curl_sync(request, body_to_log)

        try:
            # Call the actual endpoint
            response = await call_next(request)
        except Exception:
            # If the endpoint crashes, we still want to log what we can
            raise

        # Calculate duration
        duration = time.monotonic() - start_time

        # Extract tracked tables from the endpoint
        tracked_tables = []
        endpoint = request.scope.get("endpoint")
        if endpoint:
            actual_func = endpoint
            # Unwrap functools.wraps and other decorators
            depth = 0
            while hasattr(actual_func, "__wrapped__") and depth < 10:
                actual_func = actual_func.__wrapped__
                depth += 1
            
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
        # Filter out sensitive or redundant headers
        headers = [
            f"-H '{k}: {v}'" 
            for k, v in request.headers.items() 
            if k.lower() not in ("content-length", "host", "authorization")
        ]
        
        curl = f"curl -X {method} '{url}'"
        if headers:
            curl += " " + " ".join(headers)

        if body and body != b"[body capture disabled for stability]":
            try:
                json_body = json.loads(body)
                curl += f" -d '{json.dumps(json_body)}'"
            except json.JSONDecodeError:
                safe_body = body.decode('utf-8', errors='replace').replace("'", "'\\''")
                curl += f" -d '{safe_body}'"
        elif body == b"[body capture disabled for stability]":
            # Just a placeholder for now
            pass

        return curl

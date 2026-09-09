from __future__ import annotations

import re
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _sanitize_error(message: str) -> str:
    sanitized = re.sub(r"://([^:@/]+):([^@/]+)@", r"://\1:<hidden>@", message)
    sanitized = re.sub(r"password\s*=\s*[^,\s]+", "password=<hidden>", sanitized, flags=re.I)
    sanitized = re.sub(r"password\s*:\s*[^,\s]+", "password: <hidden>", sanitized, flags=re.I)
    return sanitized[:500]


def create_startup_error_app(exc: Exception) -> FastAPI:
    fallback = FastAPI(
        title="Free Time Agent API",
        version="1.0.0",
    )
    message = f"{type(exc).__name__}: {_sanitize_error(str(exc).splitlines()[0] if str(exc) else 'startup failed')}"

    def startup_error_response() -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "data": None,
                "error": {
                    "code": "backend_startup_failed",
                    "message": message,
                },
            },
        )

    @fallback.get("/health")
    def health() -> JSONResponse:
        return startup_error_response()

    @fallback.api_route(
        "/api/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    )
    def api_unavailable(path: str) -> JSONResponse:
        return startup_error_response()

    return fallback


try:
    from main import app  # noqa: E402,F401
except Exception as exc:  # pragma: no cover - Vercel runtime safety net.
    app = create_startup_error_app(exc)

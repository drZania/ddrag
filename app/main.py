"""FastAPI entry point for DDRAG milestone 1."""

import logging
import time
import uuid

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app.logging_config import configure_logging, log_request, request_id_context


settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("ddrag.http")


def _request_id(value: str | None) -> str:
    """Preserve valid UUID request IDs and generate one for other values."""

    if value:
        try:
            return str(uuid.UUID(value))
        except ValueError:
            pass
    return str(uuid.uuid4())


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach a request ID to request state, logs, and response headers."""

    async def dispatch(self, request: Request, call_next):
        request_id = _request_id(request.headers.get("X-Request-ID"))
        request.state.request_id = request_id
        token = request_id_context.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            log_request(
                logger,
                request.method,
                request.url.path,
                response.status_code,
                round((time.perf_counter() - started) * 1000, 2),
            )
            return response
        finally:
            request_id_context.reset(token)


app = FastAPI(title=settings.app_name)
app.add_middleware(RequestIdMiddleware)


@app.get("/health")
async def health() -> dict[str, str]:
    """Report application availability without checking external services."""

    return {"status": "ok"}

import inspect
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, Request, Response

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import close_db, init_db

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await init_db()
    try:
        yield
    finally:
        await close_db()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(api_router)


@app.middleware("http")
async def log_requests(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request_id = str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(request_id=request_id, path=request.url.path)

    start = time.perf_counter()
    try:
        response = await call_next(request)
        latency_ms = (time.perf_counter() - start) * 1000
        endpoint = request.scope.get("endpoint")

        file_name: str | None = None
        function_name: str | None = None
        line_number: int | None = None
        if callable(endpoint):
            try:
                source_file = inspect.getsourcefile(endpoint)
                if source_file is not None:
                    file_name = Path(source_file).name
                function_name = endpoint.__name__
                line_number = inspect.getsourcelines(endpoint)[1]
            except (OSError, TypeError):
                file_name = None
                function_name = None
                line_number = None

        logger.info(
            "request_completed",
            method=request.method,
            status_code=response.status_code,
            latency_ms=round(latency_ms, 2),
            file=file_name,
            function=function_name,
            line=line_number,
        )
        return response
    finally:
        structlog.contextvars.clear_contextvars()

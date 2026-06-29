import logging
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.feishu import router as feishu_router
from app.api.video import router as video_router
from app.core.config import settings
from app.core.database import init_db
from app.core.paths import ensure_media_dirs
from app.core.responses import UTF8JSONResponse


logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    ensure_media_dirs()
    init_db()

    app = FastAPI(
        title=settings.app_name,
        version="3.0.0",
        description="AI short-video factory for Douyin-style morning videos.",
        default_response_class=UTF8JSONResponse,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(video_router, prefix="/api/video", tags=["video"])
    app.include_router(feishu_router, prefix="/api/feishu", tags=["feishu"])
    app.mount("/media", StaticFiles(directory=settings.media_root), name="media")

    @app.middleware("http")
    async def log_api_requests(request, call_next):
        # The middleware records request status and duration without changing response bodies.
        started_at = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = int((time.monotonic() - started_at) * 1000)
            logger.exception(
                "api_request_failed method=%s path=%s duration_ms=%s",
                request.method,
                request.url.path,
                duration_ms,
            )
            raise
        duration_ms = int((time.monotonic() - started_at) * 1000)
        logger.info(
            "api_request method=%s path=%s status_code=%s duration_ms=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

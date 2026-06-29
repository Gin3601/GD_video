from pathlib import Path
import logging
import time

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.pipeline import pipeline
from app.schemas.video import (
    CreateBackgroundRequest,
    CreateBackgroundResponse,
    CreateVideoRequest,
    CreateVideoResponse,
    VideoTaskResponse,
)
from app.services.job_store import TaskNotFoundError, create_task, get_task
from app.services.video_generation_service import VideoGenerationService


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/create", response_model=CreateVideoResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_video(payload: CreateVideoRequest, background_tasks: BackgroundTasks) -> CreateVideoResponse:
    started_at = time.monotonic()
    task = create_task(payload)
    background_tasks.add_task(pipeline.run, task.id, payload)
    duration_ms = int((time.monotonic() - started_at) * 1000)
    logger.info(
        "api=/api/video/create task_id=%s provider=%s duration_ms=%s",
        task.id,
        payload.provider,
        duration_ms,
    )
    return CreateVideoResponse(
        task_id=task.id,
        status=task.status,
        status_url=f"/api/video/{task.id}",
    )


@router.post("/background/create", response_model=CreateBackgroundResponse)
async def create_background(payload: CreateBackgroundRequest) -> CreateBackgroundResponse:
    # create_background generates only a provider background asset for preview/reuse.
    started_at = time.monotonic()
    try:
        result = await VideoGenerationService().generate_background_asset(
            prompt=payload.prompt,
            output_dir=settings.siliconflow_download_dir,
            provider_name=payload.provider,
            model=payload.model,
        )
    except RuntimeError as exc:
        logger.exception("api=/api/video/background/create provider=%s failed", payload.provider)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    duration_ms = int((time.monotonic() - started_at) * 1000)
    logger.info(
        "api=/api/video/background/create provider=%s remote_task_id=%s duration_ms=%s",
        result.provider,
        result.remote_task_id,
        duration_ms,
    )
    return CreateBackgroundResponse(
        status=result.status,
        provider=result.provider,
        remote_task_id=result.remote_task_id,
        download_url=result.download_url,
        provider_cost=result.provider_cost,
        provider_response=result.provider_response,
    )


@router.get("/{task_id}", response_model=VideoTaskResponse)
async def read_video_task(task_id: str) -> VideoTaskResponse:
    try:
        task = get_task(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found") from exc

    output_url = None
    if task.output_path:
        normalized = task.output_path.replace("\\", "/")
        output_url = "/" + normalized.lstrip("/")

    return VideoTaskResponse(
        task_id=task.id,
        status=task.status,
        progress=task.progress,
        request=task.request_json,
        script=task.script,
        output_path=task.output_path,
        output_url=output_url,
        source=task.source,
        video_url=task.video_url,
        cover_url=task.cover_url,
        storage_provider=task.storage_provider,
        callback_status=task.callback_status,
        callback_error=task.callback_error,
        provider=task.provider,
        remote_task_id=task.remote_task_id,
        provider_response=task.provider_response,
        download_url=task.download_url,
        provider_cost=task.provider_cost,
        provider_status=task.provider_status,
        error=task.error,
    )


@router.get("/{task_id}/download")
async def download_video(task_id: str) -> FileResponse:
    try:
        task = get_task(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found") from exc

    if task.status != "completed" or not task.output_path:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Video is not ready")

    filename = Path(task.output_path).name
    file_path = settings.output_dir / filename
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Output file not found")

    return FileResponse(
        path=file_path,
        media_type="video/mp4",
        filename=f"{task_id}.mp4",
    )

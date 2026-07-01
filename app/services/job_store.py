from uuid import uuid4

from app.core.task_status import TaskStatus
from app.core.database import SessionLocal
from app.models.video_task import VideoTask
from app.schemas.video import CreateVideoRequest


class TaskNotFoundError(Exception):
    pass


def create_task(
    payload: CreateVideoRequest,
    *,
    source: str = "api",
    external_record_id: str | None = None,
    feishu_app_token: str | None = None,
    feishu_table_id: str | None = None,
    feishu_record_id: str | None = None,
) -> VideoTask:
    task = VideoTask(
        id=str(uuid4()),
        status=TaskStatus.QUEUED,
        request_json=payload.model_dump(mode="json"),
        progress=0,
        source=source,
        provider=payload.provider,
        provider_status="Pending",
        external_record_id=external_record_id,
        feishu_app_token=feishu_app_token,
        feishu_table_id=feishu_table_id,
        feishu_record_id=feishu_record_id,
    )
    with SessionLocal() as session:
        session.add(task)
        session.commit()
        session.refresh(task)
        return task


def get_task(task_id: str) -> VideoTask:
    with SessionLocal() as session:
        task = session.get(VideoTask, task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        session.expunge(task)
        return task


def get_task_by_feishu_record_id(record_id: str) -> VideoTask | None:
    """按飞书 record_id 查找最新的已完成任务，找不到返回 None。"""
    from sqlalchemy import select, desc
    with SessionLocal() as session:
        stmt = (
            select(VideoTask)
            .where(VideoTask.feishu_record_id == record_id)
            .order_by(desc(VideoTask.created_at))
            .limit(1)
        )
        task = session.execute(stmt).scalar_one_or_none()
        if task is not None:
            session.expunge(task)
        return task


def update_task(
    task_id: str,
    *,
    status: str | None = None,
    progress: int | None = None,
    script: str | None = None,
    output_path: str | None = None,
    video_url: str | None = None,
    cover_path: str | None = None,
    cover_url: str | None = None,
    storage_provider: str | None = None,
    storage_bucket: str | None = None,
    video_object_name: str | None = None,
    cover_object_name: str | None = None,
    callback_status: str | None = None,
    callback_error: str | None = None,
    provider: str | None = None,
    remote_task_id: str | None = None,
    provider_response: dict | None = None,
    download_url: str | None = None,
    provider_cost: float | None = None,
    provider_status: str | None = None,
    douyin_publish_status: str | None = None,
    douyin_publish_error: str | None = None,
    error: str | None = None,
) -> VideoTask:
    with SessionLocal() as session:
        task = session.get(VideoTask, task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        if status is not None:
            task.status = status
        if progress is not None:
            task.progress = progress
        if script is not None:
            task.script = script
        if output_path is not None:
            task.output_path = output_path
        if video_url is not None:
            task.video_url = video_url
        if cover_path is not None:
            task.cover_path = cover_path
        if cover_url is not None:
            task.cover_url = cover_url
        if storage_provider is not None:
            task.storage_provider = storage_provider
        if storage_bucket is not None:
            task.storage_bucket = storage_bucket
        if video_object_name is not None:
            task.video_object_name = video_object_name
        if cover_object_name is not None:
            task.cover_object_name = cover_object_name
        if callback_status is not None:
            task.callback_status = callback_status
        if callback_error is not None:
            task.callback_error = callback_error
        if provider is not None:
            task.provider = provider
        if remote_task_id is not None:
            task.remote_task_id = remote_task_id
        if provider_response is not None:
            task.provider_response = provider_response
        if download_url is not None:
            task.download_url = download_url
        if provider_cost is not None:
            task.provider_cost = provider_cost
        if provider_status is not None:
            task.provider_status = provider_status
        if douyin_publish_status is not None:
            task.douyin_publish_status = douyin_publish_status
        if douyin_publish_error is not None:
            task.douyin_publish_error = douyin_publish_error
        if error is not None:
            task.error = error
        session.commit()
        session.refresh(task)
        session.expunge(task)
        return task

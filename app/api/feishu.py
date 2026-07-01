from typing import Any, NoReturn

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from app.core.config import settings
from app.core.pipeline import pipeline
from app.schemas.feishu import (
    FeishuChallengeResponse,
    FeishuCreateFromRecordResponse,
    FeishuRecord,
    FeishuRecordFieldsRequest,
    FeishuRecordListResponse,
    FeishuRecordResponse,
    FeishuWebhookPayload,
    FeishuWebhookResponse,
)
from app.schemas.video import CreateVideoRequest
from app.services.feishu_client import FeishuAPIError, FeishuConfigError
from app.services.feishu_service import FeishuService, FeishuWebhookIgnored

logger = logging.getLogger(__name__)


router = APIRouter()
feishu_service = FeishuService()


def _to_record_response(record: dict) -> FeishuRecord:
    return FeishuRecord(record_id=record["record_id"], fields=record.get("fields", {}))


def _raise_feishu_http_error(exc: Exception) -> NoReturn:
    if isinstance(exc, FeishuConfigError):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    if isinstance(exc, FeishuAPIError):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/records", response_model=FeishuRecordListResponse)
async def list_records(
    page_size: int = Query(default=100, ge=1, le=500),
    page_token: str | None = None,
) -> FeishuRecordListResponse:
    try:
        data = await feishu_service.list_records(page_size=page_size, page_token=page_token)
    except Exception as exc:
        _raise_feishu_http_error(exc)

    return FeishuRecordListResponse(
        items=[_to_record_response(item) for item in data.get("items", [])],
        has_more=data.get("has_more", False),
        page_token=data.get("page_token"),
    )


@router.get("/records/{record_id}", response_model=FeishuRecordResponse)
async def get_record(record_id: str) -> FeishuRecordResponse:
    try:
        record = await feishu_service.get_record(record_id=record_id)
    except Exception as exc:
        _raise_feishu_http_error(exc)

    return FeishuRecordResponse(record=_to_record_response(record))


@router.post("/records", response_model=FeishuRecordResponse, status_code=status.HTTP_201_CREATED)
async def create_record(payload: FeishuRecordFieldsRequest) -> FeishuRecordResponse:
    try:
        record = await feishu_service.create_record(fields=payload.fields)
    except Exception as exc:
        _raise_feishu_http_error(exc)

    return FeishuRecordResponse(record=_to_record_response(record))


@router.patch("/records/{record_id}", response_model=FeishuRecordResponse)
async def update_record(record_id: str, payload: FeishuRecordFieldsRequest) -> FeishuRecordResponse:
    try:
        record = await feishu_service.update_record(record_id=record_id, fields=payload.fields)
    except Exception as exc:
        _raise_feishu_http_error(exc)

    return FeishuRecordResponse(record=_to_record_response(record))


@router.post("/webhook", response_model=FeishuWebhookResponse | FeishuChallengeResponse)
async def feishu_webhook(
    payload: FeishuWebhookPayload,
    background_tasks: BackgroundTasks,
) -> FeishuWebhookResponse | FeishuChallengeResponse:
    verify_token = payload.token
    if not verify_token and payload.header:
        verify_token = payload.header.get("token")

    if payload.challenge:
        feishu_service.verify_webhook_token(verify_token)
        return FeishuChallengeResponse(challenge=payload.challenge)

    try:
        feishu_service.verify_webhook_token(verify_token)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    event = payload.event or {}
    try:
        task, action = await feishu_service.create_task_from_webhook_event(event)
    except FeishuWebhookIgnored as exc:
        return FeishuWebhookResponse(ok=True, message=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if action == "background":
        background_tasks.add_task(
            _run_background_only,
            record_id=task.feishu_record_id or "",
            app_token=task.feishu_app_token,
            table_id=task.feishu_table_id,
        )
        return FeishuWebhookResponse(ok=True, message="Background task created", task_id=task.id)

    request = CreateVideoRequest(**task.request_json)
    background_tasks.add_task(pipeline.run, task.id, request)
    return FeishuWebhookResponse(ok=True, message="Task created", task_id=task.id)


async def _run_background_only(
    *,
    record_id: str,
    app_token: str | None = None,
    table_id: str | None = None,
) -> None:
    import logging
    logger = logging.getLogger(__name__)
    try:
        result = await feishu_service.create_background_from_record(
            record_id=record_id,
            app_token=app_token,
            table_id=table_id,
        )
        logger.info("action=background_only record_id=%s status=%s", record_id, result.get("status"))
    except Exception:
        logger.exception("action=background_only record_id=%s failed", record_id)


@router.post("/publish-douyin/{record_id}")
async def publish_to_douyin(
    record_id: str,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """点击「抖音上传」按鈕触发：自动生成标题/标签并上传视频到抖音。"""
    background_tasks.add_task(_do_publish_douyin, record_id=record_id)
    return {"ok": True, "message": "抖音上传已开始，请稍候查看状态字段"}


async def _do_publish_douyin(*, record_id: str) -> None:
    """异步执行抖音发布流程。"""
    from app.services.douyin_service import DouyinPublishError, DouyinService
    from app.services.job_store import get_task_by_feishu_record_id
    from app.services.llm_service import LLMService

    svc = FeishuService()

    # 1. 查找对应的已完成任务
    task = get_task_by_feishu_record_id(record_id)
    if task is None or not task.output_path:
        await svc.writeback_douyin_meta(
            record_id=record_id,
            title="",
            tags="",
            status_text="❌ 抖音发布失败：找不到已完成视频",
        )
        return

    video_path = settings.media_root.parent / task.output_path
    if not video_path.exists():
        await svc.writeback_douyin_meta(
            record_id=record_id,
            title="",
            tags="",
            status_text="❌ 抖音发布失败：视频文件不存在",
        )
        return

    # 2. 先写回状态为「发布中」
    await svc.writeback_douyin_meta(
        record_id=record_id,
        title="",
        tags="",
        status_text="🧠 AI生成标题中…",
    )

    # 3. LLM 生成抖音标题和标签
    script = task.script or ""
    req_json = task.request_json or {}
    background_name = req_json.get("background_name")
    try:
        title, tags_csv = await LLMService().generate_douyin_meta(
            script=script,
            background_name=background_name,
        )
    except Exception as exc:
        logger.exception("douyin meta generation failed record_id=%s", record_id)
        title = f"早安！{background_name or '每日一句话'}"
        tags_csv = "早安,正能量,治愈"

    # 4. 写回标题/标签，状态改为「上传中」
    await svc.writeback_douyin_meta(
        record_id=record_id,
        title=title,
        tags=tags_csv,
        status_text="📤 抖音上传中…",
    )

    # 5. 上传视频到抖音
    tags_list = [t.strip() for t in tags_csv.split(",") if t.strip()]
    try:
        result = await DouyinService().publish_video(
            video_path=video_path,
            title=title[:55],
            description=script[:500] if script else None,
            tags=tags_list or None,
        )
        if result.get("published"):
            final_status = "📱 已发布抖音 ✅"
        else:
            final_status = f"❌ 抖音发布失败：{result.get('error', '未知错误')}"
    except DouyinPublishError as exc:
        logger.exception("douyin publish failed record_id=%s", record_id)
        final_status = f"❌ 抖音发布失败：{str(exc)[:100]}"
    except Exception as exc:
        logger.exception("douyin publish unexpected error record_id=%s", record_id)
        final_status = f"❌ 抖音发布失败：{str(exc)[:100]}"

    # 6. 最终状态写回飞书
    await svc.writeback_douyin_meta(
        record_id=record_id,
        title=title,
        tags=tags_csv,
        status_text=final_status,
    )

@router.post("/create-from-record/{record_id}", response_model=FeishuCreateFromRecordResponse)
async def create_from_record(record_id: str, background_tasks: BackgroundTasks) -> FeishuCreateFromRecordResponse:
    # Detect action from the record to support both video and background modes.
    try:
        record = await feishu_service.get_record(record_id=record_id)
        fields = record.get("fields", {})
        action = feishu_service.parse_record_action(fields)
    except Exception:
        action = "video"

    if action == "background":
        background_tasks.add_task(
            _run_background_only,
            record_id=record_id,
        )
        return FeishuCreateFromRecordResponse(task_id="", status="background_queued", record_id=record_id)

    try:
        task = await feishu_service.create_task_from_record(record_id=record_id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    request = CreateVideoRequest(**task.request_json)
    background_tasks.add_task(pipeline.run, task.id, request)
    return FeishuCreateFromRecordResponse(task_id=task.id, status=task.status, record_id=record_id)

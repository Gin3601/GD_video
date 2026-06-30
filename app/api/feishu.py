from typing import NoReturn

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

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

from typing import Any

from pydantic import BaseModel, Field


class FeishuWebhookPayload(BaseModel):
    schema_: str | None = Field(default=None, alias="schema")
    header: dict[str, Any] | None = None
    event: dict[str, Any] | None = None
    challenge: str | None = None
    token: str | None = None
    type: str | None = None

    model_config = {"populate_by_name": True, "extra": "allow"}


class FeishuChallengeResponse(BaseModel):
    challenge: str


class FeishuWebhookResponse(BaseModel):
    ok: bool
    message: str
    task_id: str | None = None


class FeishuCreateFromRecordResponse(BaseModel):
    task_id: str
    status: str
    record_id: str


class FeishuRecord(BaseModel):
    record_id: str
    fields: dict[str, Any]


class FeishuRecordListResponse(BaseModel):
    items: list[FeishuRecord]
    has_more: bool = False
    page_token: str | None = None


class FeishuRecordFieldsRequest(BaseModel):
    fields: dict[str, Any]


class FeishuRecordResponse(BaseModel):
    record: FeishuRecord

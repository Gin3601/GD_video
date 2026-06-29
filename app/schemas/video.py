from typing import Literal

from pydantic import AnyUrl, BaseModel, Field


class CreateVideoRequest(BaseModel):
    type: Literal["morning"] = "morning"
    style: str = Field(default="healing", min_length=1, max_length=40)
    duration: int = Field(default=30, ge=5, le=180)
    provider: str = Field(default="local", min_length=1, max_length=32)
    model: str | None = Field(default=None, max_length=128)
    background_mode: Literal["random", "ai", "url"] = "random"
    background_url: AnyUrl | None = None
    background_name: str | None = Field(default=None, max_length=80)
    video_prompt: str | None = Field(default=None, max_length=1200)


class CreateVideoResponse(BaseModel):
    task_id: str
    status: str
    status_url: str


class CreateBackgroundRequest(BaseModel):
    # CreateBackgroundRequest is used by the frontend to generate a standalone provider background.
    provider: str = Field(default="siliconflow", min_length=1, max_length=32)
    model: str | None = Field(default=None, max_length=128)
    prompt: str = Field(min_length=1, max_length=1200)


class CreateBackgroundResponse(BaseModel):
    # CreateBackgroundResponse returns only local-storage URLs, never third-party provider URLs.
    status: str
    provider: str
    remote_task_id: str | None = None
    download_url: str | None = None
    provider_cost: float | None = None
    provider_response: dict | None = None


class VideoTaskResponse(BaseModel):
    task_id: str
    status: str
    progress: int
    request: dict
    script: str | None = None
    output_path: str | None = None
    output_url: str | None = None
    source: str | None = None
    video_url: str | None = None
    cover_url: str | None = None
    storage_provider: str | None = None
    callback_status: str | None = None
    callback_error: str | None = None
    provider: str | None = None
    remote_task_id: str | None = None
    provider_response: dict | None = None
    download_url: str | None = None
    provider_cost: float | None = None
    provider_status: str | None = None
    error: str | None = None

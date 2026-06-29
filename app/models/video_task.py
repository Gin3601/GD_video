from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class VideoTask(Base):
    __tablename__ = "video_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    request_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    script: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    external_record_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    feishu_app_token: Mapped[str | None] = mapped_column(String(128), nullable=True)
    feishu_table_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    feishu_record_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    video_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    cover_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    storage_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    storage_bucket: Mapped[str | None] = mapped_column(String(128), nullable=True)
    video_object_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    cover_object_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    callback_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    callback_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    remote_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider_response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    download_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    provider_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    provider_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

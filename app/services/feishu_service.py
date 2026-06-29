from typing import Any

from app.core.config import settings
from app.core.task_status import TaskStatus
from app.models.video_task import VideoTask
from app.schemas.video import CreateVideoRequest
from app.services.feishu_client import FeishuClient
from app.services.job_store import create_task, get_task, update_task


class FeishuWebhookIgnored(Exception):
    pass


class FeishuService:
    def __init__(self) -> None:
        self.client = FeishuClient()

    def resolve_bitable_config(
        self,
        *,
        app_token: str | None = None,
        table_id: str | None = None,
    ) -> tuple[str, str]:
        resolved_app_token = app_token or settings.feishu_base_app_token
        resolved_table_id = table_id or settings.feishu_table_id
        if not resolved_app_token or not resolved_table_id:
            raise ValueError("Feishu app_token and table_id are required")
        return resolved_app_token, resolved_table_id

    def verify_webhook_token(self, payload_token: str | None) -> None:
        expected = settings.feishu_webhook_verify_token
        if expected and payload_token != expected:
            raise PermissionError("Invalid Feishu webhook token")

    async def create_task_from_record(
        self,
        *,
        record_id: str,
        app_token: str | None = None,
        table_id: str | None = None,
    ) -> VideoTask:
        resolved_app_token, resolved_table_id = self.resolve_bitable_config(
            app_token=app_token,
            table_id=table_id,
        )

        record = await self.client.get_bitable_record(
            app_token=resolved_app_token,
            table_id=resolved_table_id,
            record_id=record_id,
        )
        fields = record.get("fields", {})
        request = CreateVideoRequest(
            type=self._normalize_video_type(
                self._field_as_text(fields.get(settings.feishu_field_type), default="morning")
            ),
            style=self._normalize_style(
                self._field_as_text(fields.get(settings.feishu_field_style), default="healing")
            ),
            duration=self._field_as_int(fields.get(settings.feishu_field_duration), default=30),
            background_mode=self._normalize_background_mode(
                self._field_as_text(
                    fields.get(settings.feishu_field_background_mode)
                    if settings.feishu_field_background_mode else None,
                    default="random",
                )
            ),
            background_url=self._field_as_url(
                fields.get(settings.feishu_field_background_url)
                if settings.feishu_field_background_url else None
            ),
            background_name=self._field_as_optional_text(
                fields.get(settings.feishu_field_background_name)
                if settings.feishu_field_background_name else None
            ),
            video_prompt=self._field_as_optional_text(
                fields.get(settings.feishu_field_video_prompt)
                if settings.feishu_field_video_prompt else None
            ),
        )
        task = create_task(
            request,
            source="feishu",
            external_record_id=record_id,
            feishu_app_token=resolved_app_token,
            feishu_table_id=resolved_table_id,
            feishu_record_id=record_id,
        )
        await self.writeback_task_result(task.id)
        return task

    async def list_records(
        self,
        *,
        page_size: int = 100,
        page_token: str | None = None,
        app_token: str | None = None,
        table_id: str | None = None,
    ) -> dict[str, Any]:
        resolved_app_token, resolved_table_id = self.resolve_bitable_config(
            app_token=app_token,
            table_id=table_id,
        )
        return await self.client.search_bitable_records(
            app_token=resolved_app_token,
            table_id=resolved_table_id,
            page_size=page_size,
            page_token=page_token,
        )

    async def get_record(
        self,
        *,
        record_id: str,
        app_token: str | None = None,
        table_id: str | None = None,
    ) -> dict[str, Any]:
        resolved_app_token, resolved_table_id = self.resolve_bitable_config(
            app_token=app_token,
            table_id=table_id,
        )
        return await self.client.get_bitable_record(
            app_token=resolved_app_token,
            table_id=resolved_table_id,
            record_id=record_id,
        )

    async def create_record(
        self,
        *,
        fields: dict[str, Any],
        app_token: str | None = None,
        table_id: str | None = None,
    ) -> dict[str, Any]:
        resolved_app_token, resolved_table_id = self.resolve_bitable_config(
            app_token=app_token,
            table_id=table_id,
        )
        return await self.client.create_bitable_record(
            app_token=resolved_app_token,
            table_id=resolved_table_id,
            fields=fields,
        )

    async def update_record(
        self,
        *,
        record_id: str,
        fields: dict[str, Any],
        app_token: str | None = None,
        table_id: str | None = None,
    ) -> dict[str, Any]:
        resolved_app_token, resolved_table_id = self.resolve_bitable_config(
            app_token=app_token,
            table_id=table_id,
        )
        return await self.client.update_bitable_record(
            app_token=resolved_app_token,
            table_id=resolved_table_id,
            record_id=record_id,
            fields=fields,
        )

    async def create_task_from_webhook_event(self, event: dict[str, Any]) -> VideoTask:
        record_id = self._extract_first(event, ["record_id", "recordId"])
        app_token = self._extract_first(event, ["app_token", "appToken"])
        table_id = self._extract_first(event, ["table_id", "tableId"])

        if not record_id:
            object_value = event.get("object") if isinstance(event.get("object"), dict) else {}
            record_id = self._extract_first(object_value, ["record_id", "recordId"])
            app_token = app_token or self._extract_first(object_value, ["app_token", "appToken"])
            table_id = table_id or self._extract_first(object_value, ["table_id", "tableId"])

        if not record_id:
            raise FeishuWebhookIgnored("Webhook event does not include a bitable record id")

        return await self.create_task_from_record(
            record_id=record_id,
            app_token=app_token,
            table_id=table_id,
        )

    async def writeback_task_result(self, task_id: str) -> None:
        task = get_task(task_id)
        if task.source != "feishu" or not task.feishu_record_id:
            return

        if not task.feishu_app_token or not task.feishu_table_id:
            update_task(
                task_id,
                callback_status="failed",
                callback_error="Missing Feishu app token or table id on task",
            )
            return

        try:
            await self._update_record_with_optional_fallback(task)
        except Exception as exc:
            update_task(task_id, callback_status="failed", callback_error=str(exc))
            return

        update_task(task_id, callback_status="completed", callback_error="")

    async def _update_record_with_optional_fallback(self, task: VideoTask) -> None:
        fields = self._build_writeback_fields(task)
        missing_field_error: Exception | None = None
        try:
            await self.client.update_bitable_record(
                app_token=task.feishu_app_token or "",
                table_id=task.feishu_table_id or "",
                record_id=task.feishu_record_id or "",
                fields=fields,
            )
            return
        except Exception as exc:
            if not self._is_missing_field_error(exc):
                raise
            missing_field_error = exc

        fallback_fields = self._drop_missing_optional_fields(fields, missing_field_error)

        if fallback_fields == fields:
            raise missing_field_error

        await self.client.update_bitable_record(
            app_token=task.feishu_app_token or "",
            table_id=task.feishu_table_id or "",
            record_id=task.feishu_record_id or "",
            fields=fallback_fields,
        )

    def _build_writeback_fields(self, task: VideoTask) -> dict[str, Any]:
        fields: dict[str, Any] = {
            settings.feishu_field_status: task.status,
        }
        if settings.feishu_field_task_id:
            fields[settings.feishu_field_task_id] = task.id
        if settings.feishu_field_script and task.script:
            fields[settings.feishu_field_script] = task.script
        if task.status == TaskStatus.COMPLETED:
            video_url = task.video_url or self._public_url(task.output_path)
            fields[settings.feishu_field_video_url] = {
                "link": video_url,
                "text": "查看视频",
            }
            if settings.feishu_field_error:
                fields[settings.feishu_field_error] = ""
        elif task.status == TaskStatus.FAILED:
            fields[settings.feishu_field_error] = task.error or "Video generation failed"
        return fields

    def _public_url(self, path: str | None) -> str:
        if not path:
            return ""
        return f"{settings.public_base_url.rstrip('/')}/{path.lstrip('/')}"

    def _is_missing_field_error(self, exc: Exception) -> bool:
        text = str(exc)
        return "FieldNameNotFound" in text or "field_name not found" in text

    def _drop_missing_optional_fields(
        self,
        fields: dict[str, Any],
        exc: Exception | None,
    ) -> dict[str, Any]:
        fallback_fields = dict(fields)
        error_text = str(exc or "")

        named_optional_fields = [
            settings.feishu_field_script,
            settings.feishu_field_task_id,
            settings.feishu_field_error,
        ]
        for optional_field in named_optional_fields:
            if optional_field and optional_field in error_text:
                fallback_fields.pop(optional_field, None)

        if fallback_fields != fields:
            return fallback_fields

        if settings.feishu_field_script:
            fallback_fields.pop(settings.feishu_field_script, None)
        return fallback_fields

    def _field_as_text(self, value: Any, *, default: str) -> str:
        if value is None:
            return default
        if isinstance(value, str):
            return value.strip() or default
        if isinstance(value, list) and value:
            first = value[0]
            if isinstance(first, dict):
                text = first.get("text") or first.get("name") or first.get("value")
                return str(text).strip() if text else default
            return str(first).strip() or default
        if isinstance(value, dict):
            text = value.get("text") or value.get("name") or value.get("value")
            return str(text).strip() if text else default
        return str(value).strip() or default

    def _field_as_optional_text(self, value: Any) -> str | None:
        text = self._field_as_text(value, default="")
        return text or None

    def _field_as_url(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            text = value.strip()
            return text if text.startswith(("http://", "https://")) else None
        if isinstance(value, list):
            for item in value:
                url = self._field_as_url(item)
                if url:
                    return url
            return None
        if isinstance(value, dict):
            for key in ("link", "url", "text"):
                raw = value.get(key)
                if isinstance(raw, str):
                    text = raw.strip()
                    if text.startswith(("http://", "https://")):
                        return text
        return None

    def _field_as_int(self, value: Any, *, default: int) -> int:
        if value is None:
            return default
        if isinstance(value, bool):
            return default
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        text = self._field_as_text(value, default=str(default))
        try:
            return int(float(text))
        except ValueError:
            return default

    def _normalize_video_type(self, value: str) -> str:
        mapping = {
            "早安": "morning",
            "早安视频": "morning",
            "morning": "morning",
        }
        return mapping.get(value.strip(), "morning")

    def _normalize_style(self, value: str) -> str:
        mapping = {
            "治愈": "healing",
            "治愈系": "healing",
            "励志": "motivational",
            "激励": "motivational",
            "平静": "calm",
            "安静": "calm",
            "电影感": "cinematic",
        }
        text = value.strip()
        return mapping.get(text, text or "healing")

    def _normalize_background_mode(self, value: str) -> str:
        mapping = {
            "ai": "ai",
            "AI": "ai",
            "AI生成": "ai",
            "大模型生成": "ai",
            "模型生成": "ai",
            "生成视频": "ai",
            "随机": "random",
            "随机素材": "random",
            "素材库": "random",
            "random": "random",
            "链接": "url",
            "指定视频": "url",
            "指定视频链接": "url",
            "视频链接": "url",
            "url": "url",
        }
        text = value.strip()
        return mapping.get(text, "random")

    def _extract_first(self, data: dict[str, Any], keys: list[str]) -> str | None:
        for key in keys:
            value = data.get(key)
            if value:
                return str(value)
        return None

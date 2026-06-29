import logging
import time
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings
from app.providers.base import ProviderError, ProviderResult, ProviderStatus, VideoProvider


logger = logging.getLogger(__name__)


class SiliconFlowProvider(VideoProvider):
    # SiliconFlowProvider contains all SiliconFlow HTTP details behind the provider contract.
    name = "siliconflow"

    def __init__(self) -> None:
        # All SiliconFlow settings come from .env-backed application settings.
        self.api_key = settings.siliconflow_api_key or settings.openai_api_key
        self.base_url = settings.siliconflow_base_url.rstrip("/")
        self.timeout = settings.siliconflow_timeout

    async def submit(
        self,
        *,
        prompt: str,
        model: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> ProviderResult:
        # submit creates a SiliconFlow video task and normalizes the provider response.
        if not self.api_key:
            raise ProviderError(
                code="PROVIDER_AUTH_MISSING",
                message="SILICONFLOW_API_KEY is required",
                provider=self.name,
            )

        payload: dict[str, Any] = {
            "model": model or settings.siliconflow_video_model,
            "prompt": prompt,
            "image_size": settings.siliconflow_video_image_size,
        }
        if settings.siliconflow_video_seed is not None:
            payload["seed"] = settings.siliconflow_video_seed
        if options:
            payload.update(options)

        started_at = time.monotonic()
        data = await self._request_json("POST", "/video/submit", json=payload)
        duration_ms = int((time.monotonic() - started_at) * 1000)
        logger.info("provider=%s action=submit duration_ms=%s", self.name, duration_ms)

        request_id = self._extract_task_id(data)
        if not request_id:
            raise ProviderError(
                code="PROVIDER_BAD_RESPONSE",
                message="SiliconFlow submit response did not include a task id",
                provider=self.name,
                raw_response=data,
            )

        return ProviderResult(
            provider=self.name,
            status=ProviderStatus.RUNNING,
            remote_task_id=request_id,
            provider_response=data,
            provider_cost=self._extract_cost(data),
        )

    async def query(self, *, remote_task_id: str) -> ProviderResult:
        # query maps SiliconFlow task states into the unified provider status vocabulary.
        started_at = time.monotonic()
        data = await self._request_json("POST", "/video/status", json={"requestId": remote_task_id})
        duration_ms = int((time.monotonic() - started_at) * 1000)
        logger.info(
            "provider=%s action=query remote_task_id=%s duration_ms=%s",
            self.name,
            remote_task_id,
            duration_ms,
        )

        status = self._normalize_status(data)
        video_url = self._extract_video_url(data)
        error = None
        if status == ProviderStatus.FAILED:
            error = {
                "code": "PROVIDER_TASK_FAILED",
                "message": "SiliconFlow video task failed",
                "provider": self.name,
                "raw_response": data,
            }

        return ProviderResult(
            provider=self.name,
            status=status,
            remote_task_id=remote_task_id,
            video_url=video_url,
            provider_response=data,
            provider_cost=self._extract_cost(data),
            error=error,
        )

    async def download(
        self,
        *,
        video_url: str,
        output_dir: Path,
        filename: str | None = None,
    ) -> ProviderResult:
        # download streams the provider video into local storage and returns the local URL.
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(httpx.URL(video_url).path).suffix.lower() or ".mp4"
        if suffix not in {".mp4", ".mov", ".mkv", ".webm"}:
            suffix = ".mp4"
        output_path = output_dir / (filename or f"siliconflow_video{suffix}")

        started_at = time.monotonic()
        bytes_written = 0
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                async with client.stream("GET", video_url) as response:
                    response.raise_for_status()
                    with output_path.open("wb") as file:
                        async for chunk in response.aiter_bytes():
                            bytes_written += len(chunk)
                            file.write(chunk)
        except httpx.TimeoutException as exc:
            raise self._provider_error("PROVIDER_DOWNLOAD_TIMEOUT", "SiliconFlow download timed out") from exc
        except httpx.NetworkError as exc:
            raise self._provider_error("PROVIDER_NETWORK_ERROR", "SiliconFlow download network error") from exc
        except httpx.HTTPStatusError as exc:
            raise self._provider_error(
                "PROVIDER_DOWNLOAD_FAILED",
                f"SiliconFlow download failed with HTTP {exc.response.status_code}",
            ) from exc

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise self._provider_error("PROVIDER_DOWNLOAD_FAILED", "Downloaded SiliconFlow video is empty")

        duration_ms = int((time.monotonic() - started_at) * 1000)
        logger.info(
            "provider=%s action=download bytes=%s duration_ms=%s",
            self.name,
            bytes_written,
            duration_ms,
        )

        return ProviderResult(
            provider=self.name,
            status=ProviderStatus.FINISHED,
            local_path=output_path,
            download_url=self._public_media_url(output_path),
        )

    async def cancel(self, *, remote_task_id: str) -> ProviderResult:
        # SiliconFlow video cancellation is exposed defensively; unsupported APIs return failure.
        try:
            data = await self._request_json("POST", "/video/cancel", json={"requestId": remote_task_id})
        except ProviderError as exc:
            if exc.code in {"PROVIDER_HTTP_ERROR", "PROVIDER_BAD_RESPONSE"}:
                raise ProviderError(
                    code="PROVIDER_CANCEL_UNSUPPORTED",
                    message="SiliconFlow cancellation is not supported by this endpoint",
                    provider=self.name,
                    raw_response=exc.raw_response,
                ) from exc
            raise

        return ProviderResult(
            provider=self.name,
            status=ProviderStatus.FAILED,
            remote_task_id=remote_task_id,
            provider_response=data,
        )

    async def _request_json(self, method: str, path: str, *, json: dict[str, Any]) -> dict[str, Any]:
        # _request_json centralizes auth headers, timeout handling, and response validation.
        started_at = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method,
                    f"{self.base_url}{path}",
                    headers=self._headers(),
                    json=json,
                )
        except httpx.TimeoutException as exc:
            raise self._provider_error("PROVIDER_TIMEOUT", "SiliconFlow API request timed out") from exc
        except httpx.NetworkError as exc:
            raise self._provider_error("PROVIDER_NETWORK_ERROR", "SiliconFlow API network error") from exc

        duration_ms = int((time.monotonic() - started_at) * 1000)
        logger.info(
            "provider=%s method=%s path=%s status_code=%s duration_ms=%s",
            self.name,
            method,
            path,
            response.status_code,
            duration_ms,
        )

        data = self._parse_json(response)
        if response.status_code >= 400:
            raise ProviderError(
                code=self._http_error_code(data),
                message=f"SiliconFlow API returned HTTP {response.status_code}",
                provider=self.name,
                raw_response=data,
            )
        if data.get("code", 0) not in (0, None):
            raise ProviderError(
                code=self._business_error_code(data),
                message=str(data.get("message") or data.get("msg") or "SiliconFlow API returned an error"),
                provider=self.name,
                raw_response=data,
            )
        return data

    def _parse_json(self, response: httpx.Response) -> dict[str, Any]:
        # SiliconFlow errors must still be JSON-like before they are stored in the task row.
        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderError(
                code="PROVIDER_BAD_RESPONSE",
                message="SiliconFlow returned a non-JSON response",
                provider=self.name,
                raw_response={"text": response.text[:500]},
            ) from exc
        if not isinstance(data, dict):
            raise ProviderError(
                code="PROVIDER_BAD_RESPONSE",
                message="SiliconFlow returned an unexpected response shape",
                provider=self.name,
                raw_response={"data": data},
            )
        return data

    def _headers(self) -> dict[str, str]:
        # Headers are defined once so every SiliconFlow call uses the same auth behavior.
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _extract_task_id(self, payload: dict[str, Any]) -> str | None:
        # SiliconFlow examples use requestId, while some gateways use request_id/task_id.
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        value = (
            payload.get("requestId")
            or payload.get("request_id")
            or payload.get("task_id")
            or data.get("requestId")
            or data.get("request_id")
            or data.get("task_id")
        )
        return str(value) if value else None

    def _extract_video_url(self, payload: dict[str, Any]) -> str | None:
        # The provider can nest the generated URL, so URL discovery is intentionally recursive.
        return self._find_url(payload)

    def _find_url(self, value: Any) -> str | None:
        # Recursion keeps provider-specific response variants out of service code.
        if isinstance(value, str):
            return value if value.startswith(("http://", "https://")) else None
        if isinstance(value, list):
            for item in value:
                url = self._find_url(item)
                if url:
                    return url
            return None
        if isinstance(value, dict):
            for key in ("url", "video_url", "videoUrl", "download_url", "downloadUrl"):
                url = self._find_url(value.get(key))
                if url:
                    return url
            for child in value.values():
                url = self._find_url(child)
                if url:
                    return url
        return None

    def _normalize_status(self, payload: dict[str, Any]) -> str:
        # Provider status aliases collapse into the five project-wide provider states.
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        raw_status = str(
            payload.get("status")
            or data.get("status")
            or data.get("task_status")
            or data.get("taskStatus")
            or ""
        ).lower()
        if raw_status in {"failed", "failure", "error", "fail"}:
            return ProviderStatus.FAILED
        if self._extract_video_url(payload) or raw_status in {"succeed", "success", "finished", "completed"}:
            return ProviderStatus.FINISHED
        if raw_status in {"pending", "queued", "created"}:
            return ProviderStatus.PENDING
        return ProviderStatus.RUNNING

    def _extract_cost(self, payload: dict[str, Any]) -> float | None:
        # Cost is optional because providers do not always return billing metadata.
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        value = payload.get("cost") or data.get("cost") or data.get("credits")
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _http_error_code(self, payload: dict[str, Any]) -> str:
        # Balance errors are promoted to a stable code for user-facing handling.
        text = str(payload).lower()
        if "balance" in text or "insufficient" in text or "余额" in text:
            return "PROVIDER_INSUFFICIENT_BALANCE"
        return "PROVIDER_HTTP_ERROR"

    def _business_error_code(self, payload: dict[str, Any]) -> str:
        # Business errors include balance failures even when HTTP status is 200.
        text = str(payload).lower()
        if "balance" in text or "insufficient" in text or "余额" in text:
            return "PROVIDER_INSUFFICIENT_BALANCE"
        return "PROVIDER_API_ERROR"

    def _provider_error(self, code: str, message: str) -> ProviderError:
        # Helper keeps low-level network/download exceptions normalized.
        return ProviderError(code=code, message=message, provider=self.name)

    def _public_media_url(self, output_path: Path) -> str:
        # Public URLs are generated only for local files under MEDIA_ROOT.
        try:
            relative_path = output_path.relative_to(settings.media_root)
            media_path = Path("media") / relative_path
        except ValueError:
            media_path = output_path
        return f"{settings.public_base_url.rstrip('/')}/{str(media_path).replace('\\', '/').lstrip('/')}"

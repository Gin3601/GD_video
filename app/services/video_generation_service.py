import asyncio
import logging
import time
from pathlib import Path

from app.core.config import settings
from app.providers import ProviderFactory
from app.providers.base import ProviderError, ProviderResult, ProviderStatus
from app.services.job_store import update_task


logger = logging.getLogger(__name__)


class VideoGenerationService:
    # VideoGenerationService orchestrates provider calls while keeping provider HTTP details isolated.
    async def generate_background(
        self,
        *,
        prompt: str,
        output_dir: Path,
        provider_name: str,
        model: str | None = None,
        task_id: str | None = None,
    ) -> Path:
        # generate_background preserves the existing pipeline entry point and returns a local file path.
        result = await self.generate_background_asset(
            prompt=prompt,
            output_dir=output_dir,
            provider_name=provider_name,
            model=model,
            task_id=task_id,
        )
        if not result.local_path:
            raise RuntimeError("Provider download did not return a local file")
        return result.local_path

    async def generate_background_asset(
        self,
        *,
        prompt: str,
        output_dir: Path,
        provider_name: str,
        model: str | None = None,
        task_id: str | None = None,
    ) -> ProviderResult:
        # generate_background_asset returns provider metadata for standalone background generation.
        provider = ProviderFactory.get(provider_name)
        started_at = time.monotonic()
        logger.info("provider=%s action=generate_background task_id=%s", provider.name, task_id)

        try:
            submit_result = await provider.submit(prompt=prompt, model=model)
            self._persist_provider_result(task_id, submit_result.status, submit_result)

            if not submit_result.remote_task_id:
                raise ProviderError(
                    code="PROVIDER_BAD_RESPONSE",
                    message="Provider did not return a remote task id",
                    provider=provider.name,
                    raw_response=submit_result.provider_response,
                )

            query_result = await self._poll_until_complete(
                provider_name=provider.name,
                remote_task_id=submit_result.remote_task_id,
                task_id=task_id,
            )
            if query_result.status == ProviderStatus.FAILED:
                raise ProviderError(
                    code=(query_result.error or {}).get("code", "PROVIDER_TASK_FAILED"),
                    message=(query_result.error or {}).get("message", "Provider task failed"),
                    provider=provider.name,
                    raw_response=query_result.provider_response,
                )
            if not query_result.video_url:
                raise ProviderError(
                    code="PROVIDER_BAD_RESPONSE",
                    message="Provider task finished without a video URL",
                    provider=provider.name,
                    raw_response=query_result.provider_response,
                )

            self._persist_provider_status(task_id, provider.name, ProviderStatus.DOWNLOADING)
            download_result = await provider.download(
                video_url=query_result.video_url,
                output_dir=settings.siliconflow_download_dir if provider.name == "siliconflow" else output_dir,
                filename=f"{task_id or submit_result.remote_task_id}.mp4",
            )

            if not download_result.local_path:
                raise ProviderError(
                    code="PROVIDER_DOWNLOAD_FAILED",
                    message="Provider download did not return a local file",
                    provider=provider.name,
                )
            normalized_result = ProviderResult(
                provider=provider.name,
                status=ProviderStatus.FINISHED,
                remote_task_id=submit_result.remote_task_id,
                local_path=download_result.local_path,
                download_url=download_result.download_url,
                provider_response=query_result.provider_response,
                provider_cost=query_result.provider_cost or submit_result.provider_cost,
            )
            self._persist_provider_result(task_id, ProviderStatus.FINISHED, normalized_result)

            duration_ms = int((time.monotonic() - started_at) * 1000)
            logger.info(
                "provider=%s action=generate_background_complete task_id=%s duration_ms=%s",
                provider.name,
                task_id,
                duration_ms,
            )
            return normalized_result
        except ProviderError as exc:
            self._persist_provider_error(task_id, exc)
            logger.exception(
                "provider=%s action=generate_background_failed task_id=%s code=%s",
                exc.provider,
                task_id,
                exc.code,
            )
            raise RuntimeError(exc.message) from exc

    async def _poll_until_complete(
        self,
        *,
        provider_name: str,
        remote_task_id: str,
        task_id: str | None,
    ):
        # _poll_until_complete owns polling cadence and timeout; the provider only performs query calls.
        provider = ProviderFactory.get(provider_name)
        deadline = time.monotonic() + settings.video_generation_timeout_seconds
        last_result = None
        while time.monotonic() < deadline:
            query_result = await provider.query(remote_task_id=remote_task_id)
            last_result = query_result
            self._persist_provider_result(task_id, query_result.status, query_result)

            if query_result.status in {ProviderStatus.FINISHED, ProviderStatus.FAILED}:
                return query_result

            await asyncio.sleep(settings.video_generation_poll_interval_seconds)

        raise ProviderError(
            code="PROVIDER_TIMEOUT",
            message="Provider video generation timed out",
            provider=provider_name,
            raw_response=last_result.provider_response if last_result else {},
        )

    def _persist_provider_result(self, task_id: str | None, status: str, result) -> None:
        # Provider metadata is optional so direct service tests can call this without a task row.
        if not task_id:
            return
        update_task(
            task_id,
            provider=result.provider,
            provider_status=status,
            remote_task_id=result.remote_task_id,
            provider_response=result.error or result.provider_response,
            download_url=result.download_url,
            provider_cost=result.provider_cost,
        )

    def _persist_provider_status(self, task_id: str | None, provider_name: str, status: str) -> None:
        # Status-only updates are used when transitioning into local download.
        if not task_id:
            return
        update_task(task_id, provider=provider_name, provider_status=status)

    def _persist_provider_error(self, task_id: str | None, exc: ProviderError) -> None:
        # Errors are stored in a normalized shape for later API and log inspection.
        if not task_id:
            return
        update_task(
            task_id,
            provider=exc.provider,
            provider_status=ProviderStatus.FAILED,
            provider_response=exc.to_dict(),
            error=exc.message,
        )

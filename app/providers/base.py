from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ProviderStatus:
    # Provider-level states use the unified vocabulary required by external video APIs.
    PENDING = "Pending"
    RUNNING = "Running"
    DOWNLOADING = "Downloading"
    FINISHED = "Finished"
    FAILED = "Failed"


class ProviderError(Exception):
    # ProviderError carries a stable error object so service/API layers do not parse text.
    def __init__(
        self,
        *,
        code: str,
        message: str,
        provider: str,
        raw_response: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.provider = provider
        self.raw_response = raw_response or {}

    def to_dict(self) -> dict[str, Any]:
        # The returned shape is safe to store in provider_response for later diagnosis.
        return {
            "code": self.code,
            "message": self.message,
            "provider": self.provider,
            "raw_response": self.raw_response,
        }


@dataclass(slots=True)
class ProviderResult:
    # ProviderResult is the normalized contract returned by every video provider.
    provider: str
    status: str
    remote_task_id: str | None = None
    video_url: str | None = None
    local_path: Path | None = None
    download_url: str | None = None
    provider_response: dict[str, Any] | None = None
    provider_cost: float | None = None
    error: dict[str, Any] | None = None


class VideoProvider(ABC):
    # VideoProvider defines the provider plugin interface used by VideoGenerationService.
    name: str

    @abstractmethod
    async def submit(
        self,
        *,
        prompt: str,
        model: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> ProviderResult:
        # submit starts a remote or local generation task and returns a normalized task id.
        raise NotImplementedError

    @abstractmethod
    async def query(self, *, remote_task_id: str) -> ProviderResult:
        # query fetches the current provider task state without applying business rules.
        raise NotImplementedError

    @abstractmethod
    async def download(
        self,
        *,
        video_url: str,
        output_dir: Path,
        filename: str | None = None,
    ) -> ProviderResult:
        # download stores provider media locally so third-party URLs are not exposed.
        raise NotImplementedError

    @abstractmethod
    async def cancel(self, *, remote_task_id: str) -> ProviderResult:
        # cancel asks a provider to stop a task when that provider supports cancellation.
        raise NotImplementedError


class LocalVideoProvider(VideoProvider):
    # LocalVideoProvider reserves the local plugin slot for current and future local GPUs.
    name = "local"

    async def submit(
        self,
        *,
        prompt: str,
        model: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> ProviderResult:
        # The current local pipeline uses local media/FFmpeg and has no async model submit step.
        raise ProviderError(
            code="LOCAL_PROVIDER_UNAVAILABLE",
            message="Local GPU video provider is not configured",
            provider=self.name,
        )

    async def query(self, *, remote_task_id: str) -> ProviderResult:
        # Local tasks do not create remote task ids, so querying is unsupported.
        raise ProviderError(
            code="LOCAL_PROVIDER_UNAVAILABLE",
            message="Local GPU video provider does not expose remote task status",
            provider=self.name,
        )

    async def download(
        self,
        *,
        video_url: str,
        output_dir: Path,
        filename: str | None = None,
    ) -> ProviderResult:
        # Local generation does not need provider media download in the current pipeline.
        raise ProviderError(
            code="LOCAL_PROVIDER_UNAVAILABLE",
            message="Local GPU video provider does not expose a downloadable URL",
            provider=self.name,
        )

    async def cancel(self, *, remote_task_id: str) -> ProviderResult:
        # Cancellation is intentionally unsupported until local GPU jobs are implemented.
        raise ProviderError(
            code="LOCAL_PROVIDER_UNAVAILABLE",
            message="Local GPU video provider cancellation is not implemented",
            provider=self.name,
        )

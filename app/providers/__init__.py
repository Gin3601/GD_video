from app.providers.base import LocalVideoProvider, VideoProvider
from app.providers.siliconflow import SiliconFlowProvider


class ProviderFactory:
    # ProviderFactory is the single extension point for video model providers.
    _providers: dict[str, type[VideoProvider]] = {
        "local": LocalVideoProvider,
        "siliconflow": SiliconFlowProvider,
    }

    @classmethod
    def get(cls, provider_name: str | None) -> VideoProvider:
        # get returns a provider instance by name and keeps business code provider-agnostic.
        normalized_name = (provider_name or "local").strip().lower()
        provider_cls = cls._providers.get(normalized_name)
        if provider_cls is None:
            supported = ", ".join(sorted(cls._providers))
            raise ValueError(f"Unsupported video provider: {normalized_name}. Supported providers: {supported}")
        return provider_cls()

    @classmethod
    def register(cls, provider_name: str, provider_cls: type[VideoProvider]) -> None:
        # register allows future providers such as kling/runway/veo to be added without rewiring services.
        cls._providers[provider_name.strip().lower()] = provider_cls

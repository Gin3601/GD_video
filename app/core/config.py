from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Video Factory V3"
    app_env: str = "production"

    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    openai_timeout_seconds: float = 45.0

    siliconflow_api_key: str | None = None
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    siliconflow_timeout: float = 60.0
    siliconflow_download_dir: Path = Path("./media/provider_downloads/siliconflow")
    siliconflow_video_model: str = "Wan-AI/Wan2.2-T2V-A14B"
    siliconflow_video_image_size: str = "720x1280"
    siliconflow_video_seed: int | None = None
    video_generation_poll_interval_seconds: float = 10.0
    video_generation_timeout_seconds: float = 900.0

    edge_tts_voice: str = "zh-CN-XiaoxiaoNeural"
    edge_tts_rate: str = "+0%"
    edge_tts_volume: str = "+0%"

    database_url: str = "sqlite:///./data/ai_video_factory.db"

    media_root: Path = Field(default=Path("./media"))
    public_base_url: str = "http://localhost:8000"
    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"
    subtitle_font_file: str | None = None
    subtitle_font_name: str = "Noto Sans CJK SC"
    subtitle_font_size: int = 16

    feishu_app_id: str | None = None
    feishu_app_secret: str | None = None
    feishu_webhook_verify_token: str | None = None
    feishu_webhook_encrypt_key: str | None = None
    feishu_base_app_token: str | None = None
    feishu_table_id: str | None = None
    feishu_field_type: str = "视频规格"
    feishu_field_style: str = "风格"
    feishu_field_duration: str | None = None
    feishu_field_video_url: str = "视频URL"
    feishu_field_status: str = "状态"
    feishu_field_error: str = "错误"
    feishu_field_task_id: str | None = "后端任务ID"
    feishu_field_script: str | None = "生成文案"
    feishu_field_action: str | None = "操作类型"
    feishu_field_background_url: str | None = "背景视频"
    feishu_field_background_name: str | None = "主题/关键词"
    feishu_field_background_mode: str | None = "背景生成方式"
    feishu_field_video_prompt: str | None = "AI背景提示词"

    cors_origins: list[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @property
    def bg_dir(self) -> Path:
        return self.media_root / "bg"

    @property
    def output_dir(self) -> Path:
        return self.media_root / "output"

    @property
    def tmp_dir(self) -> Path:
        return self.media_root / "tmp"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

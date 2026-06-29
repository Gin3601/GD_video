from app.core.config import settings


def ensure_media_dirs() -> None:
    settings.media_root.mkdir(parents=True, exist_ok=True)
    settings.bg_dir.mkdir(parents=True, exist_ok=True)
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    settings.siliconflow_download_dir.mkdir(parents=True, exist_ok=True)

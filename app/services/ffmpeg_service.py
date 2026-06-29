import random
import re
import shlex
import subprocess
from pathlib import Path

import httpx

from app.core.config import settings


VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}
MAX_BACKGROUND_BYTES = 250 * 1024 * 1024


class FFmpegService:
    def pick_background(
        self,
        *,
        video_type: str,
        style: str,
        background_name: str | None = None,
    ) -> Path:
        backgrounds = self._available_backgrounds()
        if not backgrounds:
            return self.create_default_background()

        if background_name:
            named_matches = self._match_backgrounds(backgrounds, background_name)
            if named_matches:
                return random.choice(named_matches)

        exact_matches = [
            item for item in backgrounds
            if self._contains_token(item, video_type) and self._contains_token(item, style)
        ]
        if exact_matches:
            return random.choice(exact_matches)

        style_matches = [item for item in backgrounds if self._contains_token(item, style)]
        if style_matches:
            return random.choice(style_matches)

        type_matches = [item for item in backgrounds if self._contains_token(item, video_type)]
        if type_matches:
            return random.choice(type_matches)

        non_default = [item for item in backgrounds if not item.name.startswith("default_")]
        return random.choice(non_default or backgrounds)

    async def download_background(self, url: str, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(httpx.URL(url).path).suffix.lower()
        if suffix not in VIDEO_EXTENSIONS:
            suffix = ".mp4"
        output_path = output_dir / f"background{suffix}"

        bytes_written = 0
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                with output_path.open("wb") as file:
                    async for chunk in response.aiter_bytes():
                        bytes_written += len(chunk)
                        if bytes_written > MAX_BACKGROUND_BYTES:
                            raise RuntimeError("Background video is larger than 250MB")
                        file.write(chunk)

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError("Downloaded background video is empty")
        return output_path

    def create_default_background(self) -> Path:
        output = settings.bg_dir / "default_morning_healing.mp4"
        if output.exists() and output.stat().st_size > 0:
            return output

        command = [
            settings.ffmpeg_bin,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=0xEEF7F0:s=1080x1920:r=30:d=60",
            "-vf",
            (
                "drawbox=x='mod(t*38,1280)-200':y=220:w=300:h=300:"
                "color=0xF8C7B7@0.32:t=fill,"
                "drawbox=x='920-mod(t*26,1280)':y=960:w=360:h=360:"
                "color=0x8BC6B0@0.28:t=fill,"
                "drawbox=x=120:y='mod(t*22,2100)-180':w=260:h=260:"
                "color=0xF6E7A6@0.22:t=fill,"
                "boxblur=38:1,format=yuv420p"
            ),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-movflags",
            "+faststart",
            str(output),
        ]
        subprocess.run(command, check=True, capture_output=True, text=True)
        return output

    def compose_video(
        self,
        *,
        background_path: Path,
        audio_path: Path,
        subtitle_path: Path,
        output_path: Path,
        duration: int,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        subtitle_filter = self._subtitle_filter(subtitle_path)
        video_chain = (
            "scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,"
            f"trim=duration={duration},"
            "setpts=PTS-STARTPTS,"
            "eq=brightness=-0.015:saturation=1.08,"
            f"{subtitle_filter},"
            "format=yuv420p"
        )

        command = [
            settings.ffmpeg_bin,
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            str(background_path),
            "-i",
            str(audio_path),
            "-filter_complex",
            (
                f"[0:v]{video_chain}[v];"
                f"[1:a]apad,atrim=0:{duration},asetpts=PTS-STARTPTS[a]"
            ),
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-t",
            str(duration),
            "-r",
            "30",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
        subprocess.run(command, check=True, capture_output=True, text=True)
        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError("FFmpeg did not produce a video file")
        return output_path

    def _available_backgrounds(self) -> list[Path]:
        return [
            item for item in settings.bg_dir.rglob("*")
            if item.is_file() and item.suffix.lower() in VIDEO_EXTENSIONS
        ]

    def _match_backgrounds(self, backgrounds: list[Path], text: str) -> list[Path]:
        normalized = self._normalize_token(text)
        return [
            item for item in backgrounds
            if normalized and normalized in self._search_text(item)
        ]

    def _contains_token(self, path: Path, token: str) -> bool:
        normalized = self._normalize_token(token)
        return bool(normalized and normalized in self._search_text(path))

    def _search_text(self, path: Path) -> str:
        try:
            relative = path.relative_to(settings.bg_dir)
        except ValueError:
            relative = path
        return self._normalize_token(str(relative.with_suffix("")))

    def _normalize_token(self, value: str) -> str:
        return re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", value).lower()

    def _subtitle_filter(self, subtitle_path: Path) -> str:
        path = str(subtitle_path.resolve())
        escaped_path = path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
        font_name = settings.subtitle_font_name.replace(",", "\\,")
        font_file = ""
        if settings.subtitle_font_file:
            resolved_font = Path(settings.subtitle_font_file).resolve()
            font_dir = resolved_font if resolved_font.is_dir() else resolved_font.parent
            escaped_font = str(font_dir).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
            font_file = f":fontsdir='{escaped_font}'"
        style = (
            f"FontName={font_name},"
            f"FontSize={settings.subtitle_font_size},"
            "PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H6A000000,"
            "BorderStyle=1,"
            "Outline=2,"
            "Shadow=1,"
            "Alignment=2,"
            "MarginV=210"
        )
        return f"subtitles='{escaped_path}'{font_file}:force_style={shlex.quote(style)}"

from pathlib import Path
import subprocess

import edge_tts

from app.core.config import settings


class TTSService:
    async def synthesize(self, text: str, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        last_error: Exception | None = None

        for _ in range(2):
            try:
                communicate = edge_tts.Communicate(
                    text=text,
                    voice=settings.edge_tts_voice,
                    rate=settings.edge_tts_rate,
                    volume=settings.edge_tts_volume,
                )
                await communicate.save(str(output_path))
                break
            except Exception as exc:
                last_error = exc
                if output_path.exists():
                    output_path.unlink()
        else:
            self._create_fallback_audio(text, output_path, last_error)

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError("Edge-TTS did not produce an audio file")
        return output_path

    def _create_fallback_audio(self, text: str, output_path: Path, error: Exception | None) -> None:
        duration = self._estimate_duration_seconds(text)
        command = [
            settings.ffmpeg_bin,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t",
            f"{duration:.2f}",
            "-q:a",
            "4",
            str(output_path),
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as ffmpeg_error:
            detail = str(error) if error else "unknown Edge-TTS error"
            raise RuntimeError(f"Edge-TTS failed: {detail}; fallback audio failed: {ffmpeg_error.stderr}") from ffmpeg_error

    def _estimate_duration_seconds(self, text: str) -> float:
        compact = "".join(text.split())
        chinese_chars = sum(1 for char in compact if "\u4e00" <= char <= "\u9fff")
        other_chars = max(0, len(compact) - chinese_chars)
        return max(6.0, min(180.0, chinese_chars / 4.2 + other_chars / 9.0 + 2.0))

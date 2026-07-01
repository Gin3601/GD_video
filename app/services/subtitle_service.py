import re
import subprocess
from pathlib import Path

from app.core.config import settings


class SubtitleService:
    def create_srt(self, script: str, audio_path: Path, output_path: Path, target_duration: int) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        lines = self._split_lines(script)
        audio_duration = self.probe_duration(audio_path)
        usable_duration = max(1.0, min(float(target_duration), audio_duration))

        weights = [max(1, len(line)) for line in lines]
        total_weight = sum(weights)
        cursor = 0.25
        entries = []

        for index, (line, weight) in enumerate(zip(lines, weights), start=1):
            segment = max(1.35, usable_duration * weight / total_weight)
            start = cursor
            end = min(usable_duration, start + segment)
            if index == len(lines):
                end = usable_duration
            if end <= start:
                end = start + 1.0
            entries.append((index, start, end, line))
            cursor = end + 0.05

        output_path.write_text(self._format_srt(entries), encoding="utf-8")
        return output_path

    def probe_duration(self, media_path: Path) -> float:
        command = [
            settings.ffprobe_bin,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(media_path),
        ]
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        return float(result.stdout.strip())

    def _split_lines(self, script: str) -> list[str]:
        raw_parts: list[str] = []
        for line in script.splitlines():
            raw_parts.extend(re.split(r"[，。！？!?；;,.]+", line))

        lines = []
        for part in raw_parts:
            item = part.strip()
            if not item:
                continue
            if len(item) <= 10:
                lines.append(item)
                continue
            for start in range(0, len(item), 9):
                chunk = item[start : start + 9].strip()
                if chunk:
                    lines.append(chunk)
        if not lines:
            raise ValueError("Cannot create subtitles from empty script")
        return lines

    def _format_srt(self, entries: list[tuple[int, float, float, str]]) -> str:
        blocks = []
        for index, start, end, text in entries:
            blocks.append(
                f"{index}\n"
                f"{self._timestamp(start)} --> {self._timestamp(end)}\n"
                f"{text}\n"
            )
        return "\n".join(blocks)

    def _timestamp(self, seconds: float) -> str:
        milliseconds = int(round(seconds * 1000))
        hours, remainder = divmod(milliseconds, 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        secs, millis = divmod(remainder, 1000)
        return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


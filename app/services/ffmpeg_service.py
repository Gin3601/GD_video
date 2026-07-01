import random
import re
import shlex
import subprocess
from datetime import date
from pathlib import Path

import httpx

from app.core.config import settings


# 农历月份/日期中文映射
_LUNAR_MONTHS = [
    "", "正", "二", "三", "四", "五", "六",
    "七", "八", "九", "十", "冬", "腊"
]
_LUNAR_DAYS_10 = ["", "初", "十", "廿", "三"]
_LUNAR_DAYS_1 = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]

# 中文星期
_WEEKDAY_CN = ["一", "二", "三", "四", "五", "六", "日"]

# 英文月份
_MONTH_EN = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]

# 数字转中文（用于「X月第X天」主标题）
_NUM_CN = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九",
           "十", "十一", "十二"]


def _lunar_day_str(day: int) -> str:
    """将农历日期数字转为中文，如 17 -> 十七"""
    if day <= 0 or day > 30:
        return str(day)
    if day == 10:
        return "初十"
    if day == 20:
        return "二十"
    if day == 30:
        return "三十"
    tens = day // 10
    ones = day % 10
    return _LUNAR_DAYS_10[tens] + _LUNAR_DAYS_1[ones]


def _get_lunar_date(today: date) -> tuple[int, int]:
    """获取农历月日，优先使用 lunardate 库，失败则返回近似值"""
    try:
        from lunardate import LunarDate
        lunar = LunarDate.fromSolarDate(today.year, today.month, today.day)
        return lunar.month, lunar.day
    except Exception:
        pass
    # 简单估算：农历大约比公历晚 20-50 天，无库时返回 (0, 0) 跳过农历显示
    return 0, 0


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
        date_filter = self._date_overlay_filter()
        video_chain = (
            "scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,"
            f"trim=duration={duration},"
            "setpts=PTS-STARTPTS,"
            "eq=brightness=-0.015:saturation=1.08,"
            f"{date_filter},"
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

    def _date_overlay_filter(self) -> str:
        """生成当天日期叠加的 FFmpeg drawtext 滤镜字符串（5层文字）。"""
        today = date.today()
        month_en = _MONTH_EN[today.month]
        year = today.year
        month_num = f"{today.month:02d}"
        day_num = f"{today.day:02d}"
        weekday_cn = _WEEKDAY_CN[today.weekday()]

        # 农历
        lunar_month, lunar_day = _get_lunar_date(today)
        if lunar_month > 0 and lunar_day > 0:
            lunar_str = f"农历{_LUNAR_MONTHS[lunar_month]}月{_lunar_day_str(lunar_day)}"
        else:
            lunar_str = ""

        # 主标题：「X月第X天」，计算今年第几天
        day_of_year = today.timetuple().tm_yday
        month_cn = _NUM_CN[today.month] if today.month <= 12 else str(today.month)
        # 当月第几天
        day_cn = _NUM_CN[today.day] if today.day <= 12 else str(today.day)
        main_title = f"{month_cn} 月 第 {day_cn} 天"

        fn = settings.subtitle_font_name

        def dt(text: str, x: str, y: str, size: int, color: str,
               bold: int = 0, outline: int = 3) -> str:
            escaped = text.replace("'", "\\'").replace(":", "\\:").replace("%", "\\%")
            return (
                f"drawtext=text='{escaped}'"
                f":fontfile='{self._font_path()}'"
                f":fontsize={size}"
                f":fontcolor={color}"
                f":x={x}:y={y}"
                f":borderw={outline}"
                f":bordercolor=0x000000@0.7"
                + (":box=0" if not bold else ":box=0")
            )

        layers = []

        # 1. 顶部：英文月份 + 年份，黄色，字间距宽用空格模拟
        month_spaced = "  ".join(list(month_en))
        year_spaced = "  ".join(list(str(year)))
        top_text = f"{month_spaced}   {year_spaced}"
        layers.append(dt(top_text, "(w-text_w)/2", "75", 26, "#FFD700"))

        # 2. 大字月份数字（左侧）
        layers.append(dt(month_num, "(w/2-text_w)/2+80", "130", 180, "white", bold=1, outline=4))

        # 3. 大字日期数字（右侧）
        layers.append(dt(day_num, "w/2+(w/2-text_w)/2-80", "130", 180, "white", bold=1, outline=4))

        # 4. 农历+星期（若有农历）
        if lunar_str:
            info_text = f"{lunar_str}   星期{weekday_cn}"
        else:
            info_text = f"星期{weekday_cn}"
        layers.append(dt(info_text, "(w-text_w)/2", "370", 28, "#FFD700"))

        # 5. 主标题
        layers.append(dt(main_title, "(w-text_w)/2", "440", 56, "white", bold=1, outline=4))

        return ",".join(layers)

    def _font_path(self) -> str:
        """返回可用的字体路径（用于 drawtext fontfile 参数）。"""
        if settings.subtitle_font_file:
            p = Path(settings.subtitle_font_file).resolve()
            if p.is_file():
                return str(p).replace("\\", "/").replace(":", "\\:")
        # Docker 容器内 WQY 微米黑路径
        fallbacks = [
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/wqy-microhei/wqy-microhei.ttc",
        ]
        for fb in fallbacks:
            if Path(fb).exists():
                return fb
        return ""

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
            "OutlineColour=&H00000000,"
            "BorderStyle=1,"
            "Outline=3,"
            "Shadow=2,"
            "Bold=1,"
            "Alignment=2,"
            "MarginV=180"
        )
        return f"subtitles='{escaped_path}'{font_file}:force_style={shlex.quote(style)}"

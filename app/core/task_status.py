class TaskStatus:
    QUEUED = "queued"
    RUNNING = "running"
    SCRIPT_GENERATED = "script_generated"
    VOICE_GENERATED = "voice_generated"
    SUBTITLE_GENERATED = "subtitle_generated"
    BACKGROUND_GENERATING = "background_generating"
    BACKGROUND_READY = "background_ready"
    COMPOSING = "composing"
    COMPLETED = "completed"
    FAILED = "failed"


def _bar(percent: int, total: int = 10) -> str:
    """生成字符进度条，如 30% -> △△△▷▷▷▷▷▷▷"""
    filled = round(percent / 100 * total)
    return "△" * filled + "▷" * (total - filled)


# 状态对应的中文显示（文字 + 字符进度条 + 百分比）
def _label(icon: str, text: str, percent: int) -> str:
    return f"{icon} {text}\n{_bar(percent)} {percent}%"


STATUS_LABEL: dict[str, str] = {
    TaskStatus.QUEUED:                _label("⏳", "等待中",    0),
    TaskStatus.RUNNING:               _label("🚀", "处理中",   10),
    TaskStatus.SCRIPT_GENERATED:      _label("✅", "文案已生成", 30),
    TaskStatus.VOICE_GENERATED:       _label("🎙️", "配音已完成", 50),
    TaskStatus.SUBTITLE_GENERATED:    _label("📝", "字幕已完成", 60),
    TaskStatus.BACKGROUND_GENERATING: _label("🎨", "背景生成中", 65),
    TaskStatus.BACKGROUND_READY:      _label("🌅", "背景已就绪", 70),
    TaskStatus.COMPOSING:             _label("🎥", "合成中",   85),
    TaskStatus.COMPLETED:             _label("🎉", "已完成",  100),
    TaskStatus.FAILED:                "❌ 失败",
}


TERMINAL_STATUSES = {TaskStatus.COMPLETED, TaskStatus.FAILED}

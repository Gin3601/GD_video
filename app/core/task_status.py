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


TERMINAL_STATUSES = {TaskStatus.COMPLETED, TaskStatus.FAILED}

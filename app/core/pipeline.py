import asyncio
import shutil
from pathlib import Path

from app.core.config import settings
from app.core.task_status import TaskStatus
from app.providers.base import ProviderStatus
from app.schemas.video import CreateVideoRequest
from app.services.ffmpeg_service import FFmpegService
from app.services.job_store import update_task
from app.services.llm_service import LLMService
from app.services.subtitle_service import SubtitleService
from app.services.tts_service import TTSService
from app.services.video_generation_service import VideoGenerationService


class VideoPipeline:
    def __init__(self) -> None:
        self.llm = LLMService()
        self.tts = TTSService()
        self.subtitles = SubtitleService()
        self.ffmpeg = FFmpegService()
        self.video_generator = VideoGenerationService()

    async def run(self, task_id: str, request: CreateVideoRequest) -> None:
        work_dir = settings.tmp_dir / task_id
        work_dir.mkdir(parents=True, exist_ok=True)
        audio_path = work_dir / "voice.mp3"
        subtitle_path = work_dir / "subtitles.srt"
        output_path = settings.output_dir / f"{task_id}.mp4"

        try:
            update_task(task_id, status=TaskStatus.RUNNING, progress=5, provider_status=ProviderStatus.RUNNING)
            await self._writeback_feishu(task_id)

            script = await self.llm.generate_script(request)
            update_task(task_id, status=TaskStatus.SCRIPT_GENERATED, progress=25, script=script)
            await self._writeback_feishu(task_id)

            await self.tts.synthesize(script, audio_path)
            update_task(task_id, status=TaskStatus.VOICE_GENERATED, progress=45)

            await asyncio.to_thread(
                self.subtitles.create_srt,
                script,
                audio_path,
                subtitle_path,
                request.duration,
            )
            update_task(task_id, status=TaskStatus.SUBTITLE_GENERATED, progress=60)
            await self._writeback_feishu(task_id)

            background_path = await self._prepare_background(
                task_id=task_id,
                request=request,
                script=script,
                work_dir=work_dir,
            )
            update_task(task_id, status=TaskStatus.COMPOSING, progress=72)
            await self._writeback_feishu(task_id)

            await asyncio.to_thread(
                self.ffmpeg.compose_video,
                background_path=background_path,
                audio_path=audio_path,
                subtitle_path=subtitle_path,
                output_path=output_path,
                duration=request.duration,
            )

            update_task(
                task_id,
                status=TaskStatus.COMPLETED,
                progress=100,
                output_path=str(Path("media/output") / output_path.name),
                video_url=self._public_media_url(Path("media/output") / output_path.name),
                storage_provider="local",
                provider_status=ProviderStatus.FINISHED,
            )
            await self._writeback_feishu(task_id)

            # --- 抖音自动发布 ---
            if request.publish_douyin:
                await self._publish_to_douyin(task_id=task_id, request=request, video_path=output_path)
        except Exception as exc:
            update_task(
                task_id,
                status=TaskStatus.FAILED,
                progress=100,
                provider_status=ProviderStatus.FAILED,
                error=str(exc),
            )
            await self._writeback_feishu(task_id)
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    async def _writeback_feishu(self, task_id: str) -> None:
        from app.services.feishu_service import FeishuService

        await FeishuService().writeback_task_result(task_id)

    async def _prepare_background(
        self,
        *,
        task_id: str,
        request: CreateVideoRequest,
        script: str,
        work_dir: Path,
    ) -> Path:
        if request.background_url or request.background_mode == "url":
            if not request.background_url:
                raise RuntimeError("背景来源选择了指定视频，但背景视频字段为空")
            return await self.ffmpeg.download_background(str(request.background_url), work_dir)

        if request.background_mode == "ai":
            update_task(task_id, status=TaskStatus.BACKGROUND_GENERATING, progress=65)
            await self._writeback_feishu(task_id)
            prompt = self._build_video_prompt(request=request, script=script)
            background_path = await self.video_generator.generate_background(
                prompt=prompt,
                output_dir=work_dir,
                provider_name=self._resolve_provider_name(request),
                model=request.model,
                task_id=task_id,
            )
            # 把背景视频的公网 URL 存入 task，写回飞书「背景视频」字段
            bg_public_url = self._public_media_url(background_path.relative_to(settings.media_root.parent))
            update_task(task_id, status=TaskStatus.BACKGROUND_READY, progress=70, download_url=bg_public_url)
            await self._writeback_feishu(task_id)
            return background_path

        return await asyncio.to_thread(
            self.ffmpeg.pick_background,
            video_type=request.type,
            style=request.style,
            background_name=request.background_name,
        )

    def _build_video_prompt(self, *, request: CreateVideoRequest, script: str) -> str:
        if request.video_prompt:
            return request.video_prompt.strip()

        style_map = {
            "healing": "healing, soft morning light, peaceful and warm",
            "motivational": "motivational, sunrise, energetic, hopeful",
            "calm": "calm, quiet, slow cinematic motion",
            "cinematic": "cinematic, realistic lighting, shallow depth of field",
        }
        style_prompt = style_map.get(request.style, request.style)
        script_hint = script.replace("\n", " ")[:500]
        return (
            "Vertical 9:16 short video background, no text, no subtitles, no watermark, "
            "smooth camera movement, realistic, suitable for Chinese morning short video. "
            f"Style: {style_prompt}. Visual theme based on this narration: {script_hint}"
        )

    def _resolve_provider_name(self, request: CreateVideoRequest) -> str:
        # Old clients could request AI background without a provider; keep that SiliconFlow behavior.
        if request.background_mode == "ai" and "provider" not in request.model_fields_set:
            return "siliconflow"
        return request.provider

    def _public_media_url(self, media_path: Path) -> str:
        # Public URLs point at local storage so third-party provider URLs never reach the frontend.
        normalized_path = str(media_path).replace("\\", "/").lstrip("/")
        return f"{settings.public_base_url.rstrip('/')}/{normalized_path}"

    async def _publish_to_douyin(
        self,
        *,
        task_id: str,
        request: CreateVideoRequest,
        video_path: Path,
    ) -> None:
        """视频完成后自动发布到抖音，并写回飞书状态。"""
        from app.services.douyin_service import DouyinPublishError, DouyinService
        from app.services.feishu_service import FeishuService

        logger = logging.getLogger(__name__)
        update_task(task_id, douyin_publish_status="publishing")
        await self._writeback_feishu(task_id)

        title = request.douyin_title or request.background_name or "早安视频"
        tags: list[str] | None = None
        if request.douyin_tags:
            tags = [t.strip() for t in request.douyin_tags.split(",") if t.strip()]
        description = request.script[:500] if request.script else None

        douyin = DouyinService()
        try:
            result = await douyin.publish_video(
                video_path=video_path,
                title=title[:55],
                description=description,
                tags=tags,
            )
        except DouyinPublishError as exc:
            logger.exception("douyin auto-publish failed task_id=%s", task_id)
            update_task(task_id, douyin_publish_status="failed", douyin_publish_error=str(exc))
            # 写回飞书状态
            if task_id:
                feishu = FeishuService()
                await feishu.writeback_task_result(task_id)
            return

        if result.get("success"):
            update_task(task_id, douyin_publish_status="published", douyin_publish_error="")
        else:
            update_task(
                task_id,
                douyin_publish_status="failed",
                douyin_publish_error=result.get("error", "未知错误"),
            )

        # 写回飞书（更新状态字段显示抖音发布结果）
        feishu = FeishuService()
        await feishu.writeback_task_result(task_id)


pipeline = VideoPipeline()

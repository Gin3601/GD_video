"""
抖音视频发布服务，封装 douyin-mcp-server 的 Node.js upload 脚本。
"""

import asyncio
import json
import logging
import os
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)


class DouyinPublishError(Exception):
    """抖音发布失败异常。"""

    def __init__(self, message: str, stderr: str = "") -> None:
        super().__init__(message)
        self.stderr = stderr


class DouyinService:
    """DouyinService 通过 subprocess 调用 Node.js 上传脚本。"""

    def __init__(self) -> None:
        self._node_bin = settings.douyin_node_bin
        self._upload_script = settings.douyin_upload_script
        self._data_dir = settings.douyin_data_dir
        self._timeout = settings.douyin_upload_timeout_seconds
        self._headless = settings.douyin_headless

    # ---------- public API ----------

    async def publish_video(
        self,
        video_path: Path,
        title: str,
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> dict:
        """发布视频到抖音创作者平台。

        参数
        ----
        video_path : 本地 mp4 文件绝对路径。
        title      : 视频标题（≤55 字）。
        description: 可选描述。
        tags       : 可选标签列表（不带 # 前缀）。

        返回
        ----
        {
            "success": bool,
            "title": str | None,
            "published": bool,
            "status": str | None,
            "error": str | None,
        }
        """
        self._ensure_data_dir()
        self._verify_video(video_path)

        cmd = self._build_command(video_path, title, description, tags)
        logger.info("douyin action=publish title=%s video=%s", title, video_path)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self._timeout
            )
        except asyncio.TimeoutError:
            raise DouyinPublishError(
                f"抖音发布超时（>{self._timeout}s），视频较大或网络慢",
            )

        stdout_text = stdout.decode("utf-8", errors="replace").strip()
        stderr_text = stderr.decode("utf-8", errors="replace").strip()

        logger.info(
            "douyin action=publish_result exit_code=%s stdout=%s stderr=%s",
            proc.returncode,
            stdout_text[:500],
            stderr_text[:500],
        )

        if proc.returncode == 0:
            return {
                "success": True,
                "title": title,
                "published": True,
                "status": "Published",
                "error": None,
            }
        else:
            error_msg = self._extract_error(stderr_text) or f"进程退出码 {proc.returncode}"
            return {
                "success": False,
                "title": title,
                "published": False,
                "status": "Failed",
                "error": error_msg,
            }

    # ---------- internals ----------

    def _build_command(
        self,
        video_path: Path,
        title: str,
        description: str | None,
        tags: list[str] | None,
    ) -> list[str]:
        cmd = [
            self._node_bin,
            str(self._upload_script),
            "--video", str(video_path),
            "--title", title,
            "--headless",
        ]
        if not self._headless:
            # 移除 --headless（默认 non-headless）
            cmd.remove("--headless")
        if description:
            cmd.extend(["--description", description])
        if tags:
            cmd.extend(["--tags", ",".join(tags)])
        return cmd

    def _ensure_data_dir(self) -> None:
        """确保数据目录存在，并在 Docker 环境下创建 symlink。

        douyin-uploader.js 中 cookies 路径为 __dirname/../douyin-cookies.json，
        编译后 __dirname = douyin-mcp-server/mcp-server/dist/mcp-server/，
        所以 cookies 实际位置在 douyin-mcp-server/mcp-server/dist/douyin-cookies.json。

        这里将数据目录中的文件链接到 Node 脚本期望的位置。
        """
        self._data_dir.mkdir(parents=True, exist_ok=True)

        # dist 目录（Node 脚本期望 cookies 的位置）
        upload_script_dir = self._upload_script.parent  # dist/scripts/
        dist_dir = upload_script_dir.parent  # dist/

        cookies_src = self._data_dir / "cookies.json"
        cookies_link = dist_dir / "douyin-cookies.json"

        if cookies_src.exists() and not cookies_link.exists():
            try:
                os.symlink(str(cookies_src), str(cookies_link))
                logger.info("douyin symlink created: %s -> %s", cookies_link, cookies_src)
            except OSError as exc:
                logger.warning("douyin symlink failed: %s", exc)

        chrome_data_src = self._data_dir / "chrome-user-data"
        chrome_data_link = dist_dir / "chrome-user-data"
        if chrome_data_src.exists() and not chrome_data_link.exists():
            try:
                os.symlink(str(chrome_data_src), str(chrome_data_link))
                logger.info("douyin symlink created: %s -> %s", chrome_data_link, chrome_data_src)
            except OSError as exc:
                logger.warning("douyin symlink failed: %s", exc)

    @staticmethod
    def _verify_video(video_path: Path) -> None:
        if not video_path.exists():
            raise DouyinPublishError(f"视频文件不存在: {video_path}")
        if video_path.suffix.lower() != ".mp4":
            raise DouyinPublishError(f"仅支持 mp4 格式: {video_path}")

    @staticmethod
    def _extract_error(stderr: str) -> str:
        """从 Node stderr 中提取可读错误信息。"""
        for line in reversed(stderr.splitlines()):
            line = line.strip()
            if not line:
                continue
            if "Error:" in line or "Failed" in line or "error" in line.lower():
                return line[-300:]  # 取最后 300 字符
        # fallback: 返回最后一行非空内容
        for line in reversed(stderr.splitlines()):
            line = line.strip()
            if line:
                return line[-300:]
        return "未知错误"

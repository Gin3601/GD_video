import random
import re
from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.schemas.video import CreateVideoRequest


@dataclass
class GeneratedFields:
    """LLM 同时生成的背景提示词和文案。"""
    video_prompt: str
    script: str


class LLMService:
    def __init__(self) -> None:
        self.base_url = settings.openai_base_url.rstrip("/")
        self.model = settings.openai_model
        self.api_key = settings.openai_api_key

    async def generate_script(self, request: CreateVideoRequest) -> str:
        """generate_script 仅生成文案，内部使用 request.script 干预如果已提供则直接返回。"""
        if getattr(request, "script", None):
            return request.script  # type: ignore[return-value]
        if not self.api_key:
            return self._fallback_script(request)
    
        prompt = self._build_prompt(request)
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是抖音短视频爆款文案专家，只输出适合配音的中文短句文案。",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.85,
            "max_tokens": 500,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
    
        async with httpx.AsyncClient(timeout=settings.openai_timeout_seconds) as client:
            response = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
    
        content = data["choices"][0]["message"]["content"]
        return self._normalize_script(content)
    
    def _build_prompt(self, request: CreateVideoRequest) -> str:
        theme = getattr(request, "background_name", None)
        theme_line = f"主题/关键词：{theme}\n" if theme else ""
        return (
            f"生成一个{request.duration}秒抖音早安短视频文案。\n"
            f"类型：{request.type}\n"
            f"风格：{request.style}\n"
            f"{theme_line}"
            "要求：强情绪、短句、治愈、适合清晨画面；每句不超过18个汉字；"
            "不要标题、编号、分镇、括号说明；直接输出8到14行中文文案。"
        )

    def _fallback_script(self, request: CreateVideoRequest) -> str:
        pools = {
            "healing": [
                "早安，新的光已经来了",
                "把昨天的疲惫轻轻放下",
                "今天不必太用力",
                "慢慢来，也很好",
                "风会替你翻过旧页",
                "阳光会照进心里",
                "愿你醒来有期待",
                "出门遇见温柔",
                "心里装着热爱",
                "生活就会发光",
            ],
            "inspire": [
                "早安，别低估今天",
                "你走过的每一步",
                "都在悄悄算数",
                "先把心点亮",
                "再去奔赴远方",
                "不怕慢一点",
                "只怕停在原地",
                "愿今天的你",
                "比昨天更坚定",
            ],
        }
        lines = pools.get(request.style, pools["healing"]).copy()
        random.shuffle(lines)
        selected = lines[: max(7, min(12, request.duration // 3 + 2))]
        return "\n".join(selected)

    def _normalize_script(self, text: str) -> str:
        lines = []
        for raw in text.splitlines():
            line = raw.strip()
            line = re.sub(r"^[\-\d\.\u3001\s]+", "", line)
            line = line.strip("「」\"' ")
            if line:
                lines.append(line)
        if not lines:
            raise ValueError("LLM returned empty script")
        return "\n".join(lines[:16])
    
    async def generate_fields_from_keyword(
        self,
        *,
        keyword: str,
        style: str = "healing",
        duration: int = 30,
    ) -> GeneratedFields:
        """根据「素材关键词」同时生成 AI背景提示词和视频文案。
        如果没有 API Key 则返回备用内容。
        """
        if not self.api_key:
            return self._fallback_fields(keyword=keyword, style=style, duration=duration)
    
        prompt = self._build_keyword_prompt(keyword=keyword, style=style, duration=duration)
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是短视频内容创作专家，须同时输出两内容："
                        "1. AI背景提示词：用于生成视频背景的英文描述，不超过80个单词，"
                        "必须包含: Vertical 9:16, no text, no subtitles, no watermark, smooth camera movement; "
                        "2. 视频文案：中文早安短视频配音文案，强情绪短句，每句不超过18个汉字。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.85,
            "max_tokens": 800,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
    
        async with httpx.AsyncClient(timeout=settings.openai_timeout_seconds) as client:
            response = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
    
        content = data["choices"][0]["message"]["content"]
        return self._parse_fields_response(content, keyword=keyword, style=style, duration=duration)
    
    def _build_keyword_prompt(self, *, keyword: str, style: str, duration: int) -> str:
        style_cn = {
            "healing": "治愈系",
            "motivational": "励志激励",
            "calm": "平静安心",
            "cinematic": "电影质感",
        }.get(style, style)
        return (
            f"素材关键词：{keyword}，视频风格：{style_cn}，时长：{duration}秒\n\n"
            f"请根据以上信息，创作两部分内容，按照格式输出：\n"
            "[AI背景提示词]\n"
            "（用于生成AI视频背景的英文描述，包含Vertical 9:16、背景场景、光线风格等）\n"
            "[\u89c6\u9891\u6587\u6848]\n"
            f"（中文早安配音文案，{duration}秒内容，8到8行短句，每句不超过18个汉字）"
        )
    
    def _parse_fields_response(
        self,
        content: str,
        *,
        keyword: str,
        style: str,
        duration: int,
    ) -> GeneratedFields:
        """Parse the dual-section LLM response into (video_prompt, script)."""
        video_prompt = ""
        script_lines: list[str] = []
        section = None
    
        for raw in content.splitlines():
            line = raw.strip()
            if "[AI背景提示词]" in line:
                section = "prompt"
                continue
            if "[视频文案]" in line:
                section = "script"
                continue
            if section == "prompt" and line:
                video_prompt = (video_prompt + " " + line).strip() if video_prompt else line
            elif section == "script" and line:
                cleaned = re.sub(r"^[\-\d\.\u3001\s]+", "", line).strip("「」\"' ")
                if cleaned:
                    script_lines.append(cleaned)
    
        # Fallback if parsing fails
        fb = self._fallback_fields(keyword=keyword, style=style, duration=duration)
        return GeneratedFields(
            video_prompt=video_prompt or fb.video_prompt,
            script="\n".join(script_lines[:16]) if script_lines else fb.script,
        )
    
    def _fallback_fields(self, *, keyword: str, style: str, duration: int) -> GeneratedFields:
        """Offline fallback when API key is missing or call fails."""
        style_cn = {
            "healing": "治愈系自然风光",
            "motivational": "励志上进，充满希望",
            "calm": "平静宁静，内心安宁",
            "cinematic": "电影光影，富有质感",
        }.get(style, "治愈自然")
        video_prompt = (
            f"Vertical 9:16 short video background, no text, no subtitles, no watermark, "
            f"smooth camera movement, realistic. Theme: {keyword}. Style: {style_cn}."
        )
        script = self._fallback_script.__func__(  # type: ignore[attr-defined]
            self,
            type("R", (), {"style": style, "duration": duration})(),  # type: ignore[arg-type]
        )
        return GeneratedFields(video_prompt=video_prompt, script=script)
    
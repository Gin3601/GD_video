import random
import re

import httpx

from app.core.config import settings
from app.schemas.video import CreateVideoRequest


class LLMService:
    def __init__(self) -> None:
        self.base_url = settings.openai_base_url.rstrip("/")
        self.model = settings.openai_model
        self.api_key = settings.openai_api_key

    async def generate_script(self, request: CreateVideoRequest) -> str:
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
        return (
            f"生成一个{request.duration}秒抖音早安短视频文案。\n"
            f"类型：{request.type}\n"
            f"风格：{request.style}\n"
            "要求：强情绪、短句、治愈、适合清晨画面；每句不超过18个汉字；"
            "不要标题、编号、分镜、括号说明；直接输出8到14行中文文案。"
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
            line = re.sub(r"^[\-\d\.、\s]+", "", line)
            line = line.strip("「」\"' ")
            if line:
                lines.append(line)
        if not lines:
            raise ValueError("LLM returned empty script")
        return "\n".join(lines[:16])


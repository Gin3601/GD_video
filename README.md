# AI Video Factory V3

AI Video Factory V3 is a Dockerized FastAPI service for generating Douyin-style morning short videos.

Pipeline:

1. Generate a short emotional script with an OpenAI-compatible LLM endpoint, or a local fallback when no API key is configured.
2. Generate narration with Edge-TTS.
3. Split the script into SRT subtitles.
4. Pick a random background video from `media/bg`.
5. Compose background, narration, and subtitles with FFmpeg.
6. Write the MP4 file to `media/output`.

## Quick Start

```bash
docker compose up --build
```

Create a video:

```bash
curl -X POST http://localhost:8000/api/video/create \
  -H "Content-Type: application/json" \
  -d '{"type":"morning","style":"healing","duration":30}'
```

Check the returned task:

```bash
curl http://localhost:8000/api/video/{task_id}
```

If `media/bg` has no video files, the service creates a usable default MP4 background with FFmpeg on the first job.

## OpenAI-Compatible LLM Configuration

Copy `.env.example` to `.env` or set environment variables in Docker Compose:

```bash
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
```

Any provider exposing a compatible `POST /chat/completions` API can be used by changing `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and `OPENAI_MODEL`.

## Feishu Integration

Set Feishu credentials before starting Docker:

```bash
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_WEBHOOK_VERIFY_TOKEN=xxx
FEISHU_BASE_APP_TOKEN=base_xxx
FEISHU_TABLE_ID=tbl_xxx
PUBLIC_BASE_URL=http://your-public-host:8000
```

The Bitable record should contain fields matching these configurable names:

```bash
FEISHU_FIELD_TYPE=type
FEISHU_FIELD_STYLE=style
FEISHU_FIELD_DURATION=duration
FEISHU_FIELD_VIDEO_URL=video_url
FEISHU_FIELD_STATUS=status
FEISHU_FIELD_ERROR=error
```

Create a video from a Bitable record:

```bash
curl -X POST http://localhost:8000/api/feishu/create-from-record/{record_id}
```

Frontend-friendly Bitable proxy APIs:

```text
GET    /api/feishu/records
GET    /api/feishu/records/{record_id}
POST   /api/feishu/records
PATCH  /api/feishu/records/{record_id}
```

Example frontend usage:

```js
const listRes = await fetch("/api/feishu/records?page_size=100");
const listData = await listRes.json();

const createRes = await fetch("/api/feishu/records", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    fields: {
      type: "morning",
      style: "healing",
      duration: 30,
      status: "pending"
    }
  })
});
const created = await createRes.json();
```

Webhook endpoint:

```text
POST /api/feishu/webhook
```

After generation, tasks with `source=feishu` write the video URL, status, and error fields back to the configured Bitable record.

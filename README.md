# AI 视频工厂 V3

AI 视频工厂 V3 是一个基于 Docker 部署的 FastAPI 服务，用于自动生成抖音风格的早安短视频。

## 核心功能

- **LLM 脚本生成**：通过 OpenAI 兼容接口生成情感文案脚本，支持本地降级方案
- **AI 视频生成**：集成 SiliconFlow 等云端视频生成模型（如 Wan2.2 文生视频）
- **Edge-TTS 语音合成**：使用微软 Edge-TTS 引擎生成旁白配音
- **SRT 字幕生成**：自动将脚本拆分为 SRT 字幕文件
- **FFmpeg 视频合成**：将背景视频、配音、字幕合成为最终 MP4
- **飞书多维表格集成**：支持通过飞书多维表格管理和触发视频生成任务
- **异步任务管理**：所有视频生成任务均为异步执行，支持进度查询

## 视频生成流程

1. 调用 OpenAI 兼容的 LLM 接口生成短文案脚本
2. 使用 Edge-TTS 生成旁白音频
3. 将脚本拆分为 SRT 字幕
4. 从 `media/bg` 目录随机选取背景视频（或使用 AI 生成背景）
5. 通过 FFmpeg 合成背景、配音和字幕
6. 输出 MP4 文件到 `media/output` 目录

## 快速开始

### Docker 部署（推荐）

```bash
docker compose up --build
```

### 本地开发

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 创建视频

```bash
curl -X POST http://localhost:8000/api/video/create \
  -H "Content-Type: application/json" \
  -d '{"type":"morning","style":"healing","duration":30}'
```

### 查询任务状态

```bash
curl http://localhost:8000/api/video/{task_id}
```

### 下载视频

```bash
curl http://localhost:8000/api/video/{task_id}/download
```

> 如果 `media/bg` 目录下没有视频文件，服务会在首次任务时自动使用 FFmpeg 生成一个默认背景视频。

## API 接口

### 视频相关

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/video/create` | 创建视频生成任务 |
| GET | `/api/video/{task_id}` | 查询任务状态与进度 |
| GET | `/api/video/{task_id}/download` | 下载已完成的视频 |
| POST | `/api/video/background/create` | 生成 AI 背景素材 |
| GET | `/health` | 健康检查 |

### 飞书多维表格

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/feishu/records` | 获取多维表格记录列表 |
| GET | `/api/feishu/records/{record_id}` | 获取单条记录 |
| POST | `/api/feishu/records` | 创建新记录 |
| PATCH | `/api/feishu/records/{record_id}` | 更新记录 |
| POST | `/api/feishu/create-from-record/{record_id}` | 从多维表格记录创建视频 |
| POST | `/api/feishu/webhook` | 飞书 Webhook 回调 |

## 环境配置

复制 `.env.example` 为 `.env` 或直接在 Docker Compose 中设置环境变量。

### LLM 配置

支持任何兼容 OpenAI `POST /chat/completions` 接口的服务商：

```bash
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
```

### SiliconFlow AI 视频生成配置

```bash
SILICONFLOW_API_KEY=
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
SILICONFLOW_TIMEOUT=60
SILICONFLOW_VIDEO_MODEL=Wan-AI/Wan2.2-T2V-A14B
SILICONFLOW_VIDEO_IMAGE_SIZE=720x1280
VIDEO_GENERATION_POLL_INTERVAL_SECONDS=10
VIDEO_GENERATION_TIMEOUT_SECONDS=900
```

### TTS 语音合成配置

```bash
EDGE_TTS_VOICE=zh-CN-XiaoxiaoNeural
```

### 飞书集成配置

如需启用飞书多维表格功能，请先配置以下凭据：

```bash
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_WEBHOOK_VERIFY_TOKEN=xxx
FEISHU_WEBHOOK_ENCRYPT_KEY=xxx
FEISHU_BASE_APP_TOKEN=base_xxx
FEISHU_TABLE_ID=tbl_xxx
PUBLIC_BASE_URL=http://your-public-host:8000
```

多维表格字段名可自定义配置：

```bash
FEISHU_FIELD_TYPE=type
FEISHU_FIELD_STYLE=style
FEISHU_FIELD_DURATION=duration
FEISHU_FIELD_VIDEO_URL=video_url
FEISHU_FIELD_STATUS=status
FEISHU_FIELD_ERROR=error
```

### 字幕与其他配置

```bash
SUBTITLE_FONT_FILE=
SUBTITLE_FONT_NAME=Noto Sans CJK SC
SUBTITLE_FONT_SIZE=16
FFMPEG_BIN=ffmpeg
FFPROBE_BIN=ffprobe
```

## 项目结构

```
app/
├── api/              # API 路由层
│   ├── video.py      # 视频相关接口
│   └── feishu.py     # 飞书相关接口
├── core/             # 核心配置
│   ├── config.py     # 环境变量与配置管理
│   ├── database.py   # 数据库初始化
│   ├── pipeline.py   # 视频生成流水线
│   └── paths.py      # 路径管理
├── models/           # 数据库模型
├── providers/        # 视频生成服务商
│   ├── base.py       # 服务商基类
│   └── siliconflow.py # SiliconFlow 实现
├── schemas/          # Pydantic 请求/响应模型
└── services/         # 业务服务层
    ├── feishu_client.py       # 飞书 API 客户端
    ├── feishu_service.py      # 飞书业务服务
    ├── ffmpeg_service.py      # FFmpeg 合成服务
    ├── llm_service.py         # LLM 脚本生成
    ├── subtitle_service.py    # 字幕处理
    ├── tts_service.py         # TTS 语音合成
    ├── tts_cosyvoice.py       # CosyVoice 语音合成
    └── video_generation_service.py  # AI 视频生成
```

## 技术栈

- **Web 框架**：FastAPI + Uvicorn
- **数据库**：SQLite + SQLAlchemy
- **语音合成**：Edge-TTS
- **视频处理**：FFmpeg
- **AI 视频生成**：SiliconFlow（Wan2.2）
- **LLM**：OpenAI 兼容接口
- **容器化**：Docker

## 飞书前端示例

```js
// 获取记录列表
const listRes = await fetch("/api/feishu/records?page_size=100");
const listData = await listRes.json();

// 创建新记录
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

生成完成后，`source=feishu` 的任务会自动将视频链接、状态和错误信息回写到对应的多维表格记录中。

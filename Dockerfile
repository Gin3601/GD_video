FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# ========== 安装系统依赖 ==========
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null; \
    sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null; \
    apt-get update \
    && apt-get install -y --no-install-recommends \
      ffmpeg \
      fonts-wqy-microhei \
      ca-certificates \
      curl \
      gnupg \
      # Puppeteer/Chromium 运行时依赖
      libnss3 libnspr4 libatk1.0-0t64 libatk-bridge2.0-0t64 \
      libcups2t64 libdrm2 libdbus-1-3 libxkbcommon0 \
      libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
      libgbm1 libpango-1.0-0 libcairo2 libasound2t64 \
    && rm -rf /var/lib/apt/lists/*

# ========== 安装 Node.js 20.x ==========
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && node --version && npm --version

# ========== Python 依赖 ==========
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com -r requirements.txt

# ========== Node.js 依赖（使用 npmmirror 下载 Chromium） ==========
# PUPPETEER_DOWNLOAD_HOST 环境变量让 Puppeteer 从 npmmirror 下载 Chromium
COPY douyin-mcp-server/mcp-server/package.json douyin-mcp-server/mcp-server/package-lock.json* ./douyin-mcp-server/mcp-server/
RUN cd douyin-mcp-server/mcp-server \
    && PUPPETEER_DOWNLOAD_HOST=https://npmmirror.com/mirrors \
       npm install --registry=https://registry.npmmirror.com

# ========== 编译 TypeScript ==========
COPY douyin-mcp-server/ ./douyin-mcp-server/
RUN cd douyin-mcp-server/mcp-server && npm run build

# ========== 应用代码 ==========
COPY . .

# ========== 创建 douyin 数据目录 symlink ==========
RUN mkdir -p /app/douyin_data \
    && ln -sf /app/douyin_data/cookies.json /app/douyin-mcp-server/mcp-server/dist/douyin-cookies.json \
    && ln -sf /app/douyin_data/chrome-user-data /app/douyin-mcp-server/mcp-server/dist/chrome-user-data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

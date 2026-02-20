FROM node:22-slim

# 安装系统依赖 (Python, FFmpeg, Git 及无头浏览器运行所需)
RUN apt-get update && apt-get install -y \
    git \
    python3 python3-pip python3-venv \
    ffmpeg \
    wget gnupg \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

# 工作目录
WORKDIR /app

# 安装 Node.js 核心库 (openclaw)
COPY package*.json ./
RUN npm install

# 安装 Python 的依赖与 Playwright 浏览器
RUN pip3 install --no-cache-dir playwright undetected-chromedriver --break-system-packages && \
    playwright install chromium --with-deps

# 复制整个裁剪后的云端环境
COPY . .

# 设置环境变量，指引 OpenClaw 到当前目录
ENV OPENCLAW_HOME=/app
ENV PORT=8080
ENV HOST=0.0.0.0

# 暴露给 Zeabur 监听的默认端口
EXPOSE 8080

# 启动 OpenClaw Gateway
CMD ["npx", "openclaw", "gateway", "--port", "8080", "--host", "0.0.0.0"]

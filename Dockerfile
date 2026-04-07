# Multi-stage Dockerfile for Claude Code Telegram Bot with Local Bun Implementation
# 支持本地 Bun 实现的 Claude Code + Telegram Bot

# ==================== Stage 1: Build Bun Project ====================
FROM oven/bun:1.1-alpine AS bun-builder

WORKDIR /build

# 复制 claudecode 项目文件
COPY claudecode/package*.json ./
RUN bun install --frozen-lockfile || bun install

# 复制源码
COPY claudecode/ ./

# ==================== Stage 2: Python Dependencies ====================
FROM python:3.11-slim AS python-deps

WORKDIR /deps

# 安装编译依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制 requirements 并安装
COPY claude-code-telegram/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ==================== Stage 3: Production Image ====================
FROM python:3.11-slim AS production

# 避免交互式配置提示
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    sqlite3 \
    # 添加常用工具，让 Claude 有更多能力
    vim \
    nano \
    tree \
    jq \
    unzip \
    zip \
    wget \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 安装 Bun (从官方镜像复制)
COPY --from=oven/bun:1.1-alpine /usr/local/bin/bun /usr/local/bin/bun
COPY --from=oven/bun:1.1-alpine /usr/local/bin/bunx /usr/local/bin/bunx

# 创建非 root 用户（安全最佳实践）
RUN groupadd -r claudebot && useradd -r -g claudebot -m -s /bin/bash claudebot

# 创建必要的目录
RUN mkdir -p /app/claude-code-telegram \
    /app/claudecode \
    /data \
    /projects \
    && chown -R claudebot:claudebot /app /data /projects

# 设置工作目录
WORKDIR /app/claude-code-telegram

# 复制 Python 依赖
COPY --from=python-deps /root/.local /home/claudebot/.local
RUN chown -R claudebot:claudebot /home/claudebot/.local

# 复制 Python 路径
ENV PATH=/home/claudebot/.local/bin:$PATH
ENV PYTHONPATH=/app/claude-code-telegram

# 复制 Telegram Bot 代码
COPY --chown=claudebot:claudebot claude-code-telegram/ .

# 复制 Bun 项目
COPY --chown=claudebot:claudebot --from=bun-builder /build /app/claudecode

# 设置环境变量
ENV CLAUDE_LOCAL_PROJECT_PATH=/app/claudecode
ENV USE_LOCAL_BUN=true
ENV DATABASE_URL=sqlite:////data/bot.db
ENV APPROVED_DIRECTORY=/projects
ENV HOME=/home/claudebot

# 创建启动脚本
RUN cat > /app/start.sh << 'EOF'
#!/bin/bash
set -e

echo "🚀 Starting Claude Code Telegram Bot..."
echo "📁 Working directory: $(pwd)"
echo "👤 Running as: $(whoami)"
echo "🔧 Bun version: $(bun --version)"
echo "🐍 Python version: $(python --version)"

# 确保数据目录存在且有权限
mkdir -p /data
mkdir -p /projects

# 初始化数据库（如果不存在）
if [ ! -f /data/bot.db ]; then
    echo "📦 Initializing database..."
    touch /data/bot.db
fi

# 检查环境变量
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "❌ ERROR: TELEGRAM_BOT_TOKEN is not set!"
    echo "Please set the TELEGRAM_BOT_TOKEN environment variable."
    exit 1
fi

if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "⚠️  WARNING: ANTHROPIC_API_KEY is not set!"
    echo "The bot may not function properly without an API key."
fi

echo "✅ Environment check passed"
echo "🤖 Starting bot..."
echo ""

# 启动 Bot
exec python -m src.main
EOF

RUN chmod +x /app/start.sh

# 切换到非 root 用户
USER claudebot

# 暴露端口（如果需要 API 服务器）
EXPOSE 8080

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# 启动命令
ENTRYPOINT ["/app/start.sh"]

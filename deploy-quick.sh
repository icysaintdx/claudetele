#!/bin/bash
# Claude Code Telegram Bot 快速部署脚本（精简版）
# 适用于已有 Docker 环境的服务器

set -e

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}Claude Code Telegram Bot Docker 部署${NC}"
echo "========================================"

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}安装 Docker...${NC}"
    curl -fsSL https://get.docker.com | sh
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${YELLOW}安装 Docker Compose...${NC}"
    apt-get update && apt-get install -y docker-compose-plugin
    ln -sf /usr/libexec/docker/cli-plugins/docker-compose /usr/local/bin/docker-compose
fi

# 创建目录
INSTALL_DIR="${1:-/opt/claude-code-telegram}"
mkdir -p "$INSTALL_DIR"/{data,projects}

# 复制文件
cp -r claude-code-telegram claudecode Dockerfile docker-compose.yml "$INSTALL_DIR/" 2>/dev/null || {
    echo -e "${RED}错误：找不到项目文件${NC}"
    echo "请确保当前目录包含："
    echo "  - claude-code-telegram/"
    echo "  - claudecode/"
    echo "  - Dockerfile"
    echo "  - docker-compose.yml"
    exit 1
}

# 创建环境变量文件
if [ ! -f "$INSTALL_DIR/.env" ]; then
    cat > "$INSTALL_DIR/.env" << 'EOF'
# 必需配置
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_BOT_USERNAME=your_bot_username
ANTHROPIC_API_KEY=your_api_key

# 可选配置
ANTHROPIC_BASE_URL=https://api.anthropic.com
AGENTIC_MODE=true
VERBOSE_LEVEL=1
ALLOWED_USERS=
LOG_LEVEL=INFO
EOF
    echo -e "${YELLOW}请编辑 $INSTALL_DIR/.env 填入你的配置${NC}"
fi

# 设置权限
chown -R 1000:1000 "$INSTALL_DIR/data" "$INSTALL_DIR/projects"

# 构建和启动
cd "$INSTALL_DIR"
echo -e "${YELLOW}构建 Docker 镜像...${NC}"
docker-compose build

echo -e "${YELLOW}启动服务...${NC}"
docker-compose up -d

echo ""
echo -e "${GREEN}✅ 部署完成！${NC}"
echo ""
echo "📁 安装目录: $INSTALL_DIR"
echo "📝 配置文件: $INSTALL_DIR/.env"
echo "📊 查看日志: docker-compose logs -f"
echo "🛑 停止服务: docker-compose down"
echo ""
echo -e "${YELLOW}⚠️  请编辑 .env 文件并填入你的 Telegram Bot Token 和 API Key，然后重启服务${NC}"

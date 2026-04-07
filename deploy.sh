#!/bin/bash
# Claude Code Telegram Bot Docker 部署脚本
# 用于 Debian/Ubuntu 服务器

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否以 root 运行
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "此脚本需要以 root 权限运行"
        print_info "请使用: sudo bash deploy.sh"
        exit 1
    fi
}

# 安装 Docker 和 Docker Compose
install_docker() {
    print_info "检查 Docker 安装..."
    
    if command -v docker &> /dev/null; then
        print_success "Docker 已安装: $(docker --version)"
    else
        print_info "正在安装 Docker..."
        curl -fsSL https://get.docker.com | sh
        systemctl enable docker
        systemctl start docker
        print_success "Docker 安装完成"
    fi
    
    if command -v docker-compose &> /dev/null; then
        print_success "Docker Compose 已安装: $(docker-compose --version)"
    else
        print_info "正在安装 Docker Compose..."
        apt-get update
        apt-get install -y docker-compose-plugin
        # 创建兼容的软链接
        ln -sf /usr/libexec/docker/cli-plugins/docker-compose /usr/local/bin/docker-compose
        print_success "Docker Compose 安装完成"
    fi
}

# 创建目录结构
setup_directories() {
    print_info "创建目录结构..."
    
    INSTALL_DIR="${INSTALL_DIR:-/opt/claude-code-telegram}"
    
    mkdir -p "$INSTALL_DIR"/{data,projects,config,logs}
    
    print_success "目录结构已创建: $INSTALL_DIR"
}

# 复制项目文件
copy_project_files() {
    print_info "复制项目文件..."
    
    INSTALL_DIR="${INSTALL_DIR:-/opt/claude-code-telegram}"
    
    # 检查源文件是否存在
    if [ ! -d "claude-code-telegram" ] || [ ! -d "claudecode" ]; then
        print_error "未找到项目文件!"
        print_info "请确保在包含 claude-code-telegram 和 claudecode 目录的文件夹中运行此脚本"
        exit 1
    fi
    
    # 复制项目文件
    cp -r claude-code-telegram "$INSTALL_DIR/"
    cp -r claudecode "$INSTALL_DIR/"
    cp Dockerfile "$INSTALL_DIR/"
    cp docker-compose.yml "$INSTALL_DIR/"
    cp deploy.sh "$INSTALL_DIR/" 2>/dev/null || true
    
    # 设置权限
    chown -R 1000:1000 "$INSTALL_DIR/data" "$INSTALL_DIR/projects" "$INSTALL_DIR/logs"
    chmod 755 "$INSTALL_DIR/data" "$INSTALL_DIR/projects" "$INSTALL_DIR/logs"
    
    print_success "项目文件已复制到: $INSTALL_DIR"
}

# 创建环境变量文件
create_env_file() {
    print_info "创建环境变量文件..."
    
    INSTALL_DIR="${INSTALL_DIR:-/opt/claude-code-telegram}"
    ENV_FILE="$INSTALL_DIR/.env"
    
    if [ -f "$ENV_FILE" ]; then
        print_warning "环境变量文件已存在: $ENV_FILE"
        read -p "是否覆盖? (y/N): " overwrite
        if [[ ! "$overwrite" =~ ^[Yy]$ ]]; then
            print_info "保留现有环境变量文件"
            return
        fi
    fi
    
    cat > "$ENV_FILE" << 'EOF'
# Claude Code Telegram Bot 环境变量配置
# 请修改以下值为你的实际配置

# === 必需配置 ===
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_BOT_USERNAME=your_bot_username

# === Claude API 配置 ===
# 支持 Anthropic 官方 API 或第三方兼容 API（如 MiniMax、OpenRouter）
ANTHROPIC_API_KEY=your_api_key_here
ANTHROPIC_BASE_URL=https://api.anthropic.com
# ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic  # MiniMax 示例
ANTHROPIC_MODEL=claude-3-opus-20240229
# ANTHROPIC_MODEL=MiniMax-M2.7-highspeed  # MiniMax 示例

# === 安全配置 ===
# 允许的 Telegram 用户 ID（逗号分隔，留空允许所有用户）
ALLOWED_USERS=

# 是否禁用安全检查（生产环境建议保持 false）
DISABLE_SECURITY_PATTERNS=false
DISABLE_TOOL_VALIDATION=false

# === 功能配置 ===
AGENTIC_MODE=true
VERBOSE_LEVEL=1
ENABLE_GIT_INTEGRATION=true
ENABLE_FILE_UPLOADS=true
ENABLE_QUICK_ACTIONS=true
ENABLE_IMAGE_UPLOADS=true
ENABLE_CONVERSATION_MODE=true
ENABLE_VOICE_MESSAGES=false

# === 限制配置 ===
CLAUDE_TIMEOUT_SECONDS=300
CLAUDE_MAX_TURNS=50
CLAUDE_MAX_COST_PER_USER=10.0
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60

# === API 服务器配置（可选）===
ENABLE_API_SERVER=false
API_SERVER_PORT=8080

# === 日志配置 ===
LOG_LEVEL=INFO
ENVIRONMENT=production
DEBUG=false
EOF
    
    print_success "环境变量文件已创建: $ENV_FILE"
    print_warning "请编辑 $ENV_FILE 文件，填入你的实际配置"
}

# 构建 Docker 镜像
build_image() {
    print_info "构建 Docker 镜像..."
    
    INSTALL_DIR="${INSTALL_DIR:-/opt/claude-code-telegram}"
    cd "$INSTALL_DIR"
    
    docker-compose build --no-cache
    
    print_success "Docker 镜像构建完成"
}

# 启动服务
start_service() {
    print_info "启动 Claude Code Telegram Bot..."
    
    INSTALL_DIR="${INSTALL_DIR:-/opt/claude-code-telegram}"
    cd "$INSTALL_DIR"
    
    # 加载环境变量
    if [ -f ".env" ]; then
        export $(grep -v '^#' .env | xargs)
    fi
    
    # 启动服务
    docker-compose up -d
    
    print_success "服务已启动"
    
    # 显示状态
    sleep 2
    docker-compose ps
    
    echo ""
    print_info "查看日志: docker-compose logs -f"
    print_info "停止服务: docker-compose down"
    print_info "重启服务: docker-compose restart"
}

# 创建 systemd 服务（可选）
create_systemd_service() {
    print_info "创建 systemd 服务..."
    
    INSTALL_DIR="${INSTALL_DIR:-/opt/claude-code-telegram}"
    
    cat > /etc/systemd/system/claude-telegram-bot.service << EOF
[Unit]
Description=Claude Code Telegram Bot
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    systemctl enable claude-telegram-bot.service
    
    print_success "systemd 服务已创建"
    print_info "使用 systemctl start claude-telegram-bot 启动"
    print_info "使用 systemctl stop claude-telegram-bot 停止"
}

# 显示使用说明
show_usage() {
    INSTALL_DIR="${INSTALL_DIR:-/opt/claude-code-telegram}"
    
    echo ""
    echo "=========================================="
    echo "  Claude Code Telegram Bot 部署完成!"
    echo "=========================================="
    echo ""
    echo "📁 安装目录: $INSTALL_DIR"
    echo ""
    echo "📋 常用命令:"
    echo "  cd $INSTALL_DIR"
    echo "  docker-compose logs -f        # 查看实时日志"
    echo "  docker-compose logs --tail 100 # 查看最后100行日志"
    echo "  docker-compose ps             # 查看服务状态"
    echo "  docker-compose down           # 停止服务"
    echo "  docker-compose up -d          # 启动服务"
    echo "  docker-compose restart        # 重启服务"
    echo "  docker-compose pull && docker-compose up -d  # 更新并重启"
    echo ""
    echo "🔧 配置文件:"
    echo "  环境变量: $INSTALL_DIR/.env"
    echo "  数据库:   $INSTALL_DIR/data/bot.db"
    echo "  项目目录: $INSTALL_DIR/projects/"
    echo "  日志:     $INSTALL_DIR/logs/"
    echo ""
    echo "📊 监控:"
    echo "  docker stats claude-telegram-bot  # 查看资源使用"
    echo ""
    echo "🔄 更新:"
    echo "  1. 更新代码文件"
    echo "  2. docker-compose build --no-cache"
    echo "  3. docker-compose up -d"
    echo ""
    echo "⚠️  注意事项:"
    echo "  - 请确保 $INSTALL_DIR/.env 文件中的配置正确"
    echo "  - 项目文件存储在 $INSTALL_DIR/projects/"
    echo "  - 数据库自动备份到 $INSTALL_DIR/data/"
    echo ""
}

# 主函数
main() {
    echo "=========================================="
    echo "  Claude Code Telegram Bot Docker 部署"
    echo "=========================================="
    echo ""
    
    # 检查 root 权限
    check_root
    
    # 设置安装目录（可通过环境变量覆盖）
    export INSTALL_DIR="${INSTALL_DIR:-/opt/claude-code-telegram}"
    
    # 安装 Docker
    install_docker
    
    # 设置目录
    setup_directories
    
    # 复制项目文件
    copy_project_files
    
    # 创建环境变量文件
    create_env_file
    
    # 询问是否立即构建和启动
    echo ""
    read -p "是否立即构建 Docker 镜像? (Y/n): " build_now
    if [[ ! "$build_now" =~ ^[Nn]$ ]]; then
        build_image
        
        # 询问是否创建 systemd 服务
        read -p "是否创建 systemd 服务? (y/N): " create_systemd
        if [[ "$create_systemd" =~ ^[Yy]$ ]]; then
            create_systemd_service
        fi
        
        # 询问是否立即启动
        read -p "是否立即启动服务? (Y/n): " start_now
        if [[ ! "$start_now" =~ ^[Nn]$ ]]; then
            start_service
        fi
    fi
    
    # 显示使用说明
    show_usage
}

# 如果直接运行此脚本
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi

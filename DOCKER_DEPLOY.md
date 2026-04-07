# Docker 部署指南与权限问题解决方案

本文档详细介绍如何将 Claude Code Telegram Bot 部署到 Linux 服务器的 Docker 中，并解决权限相关问题。

---

## 📋 目录

1. [快速部署](#快速部署)
2. [目录结构](#目录结构)
3. [权限问题详解](#权限问题详解)
4. [工具调用权限](#工具调用权限)
5. [文件编辑写入权限](#文件编辑写入权限)
6. [故障排查](#故障排查)
7. [安全建议](#安全建议)

---

## 快速部署

### 前提条件

- Debian/Ubuntu 服务器（或其他 Linux 发行版）
- root 或 sudo 权限
- 至少 2GB RAM，10GB 磁盘空间

### 一键部署

```bash
# 1. 将项目文件上传到服务器
# 假设你已经将以下文件上传到 /root/claude-suite/ 目录：
# - claude-code-telegram/
# - claudecode/
# - Dockerfile
# - docker-compose.yml
# - deploy.sh

# 2. 进入目录
cd /root/claude-suite

# 3. 运行部署脚本
chmod +x deploy.sh
sudo bash deploy.sh

# 4. 编辑环境变量
sudo nano /opt/claude-code-telegram/.env

# 5. 启动服务
cd /opt/claude-code-telegram
sudo docker-compose up -d
```

### 手动部署

如果你不想使用脚本，可以手动部署：

```bash
# 1. 安装 Docker
curl -fsSL https://get.docker.com | sh

# 2. 创建目录
mkdir -p /opt/claude-code-telegram/{data,projects,config,logs}

# 3. 复制项目文件
cp -r claude-code-telegram /opt/claude-code-telegram/
cp -r claudecode /opt/claude-code-telegram/
cp Dockerfile /opt/claude-code-telegram/
cp docker-compose.yml /opt/claude-code-telegram/

# 4. 创建 .env 文件
# （参考 deploy.sh 中的示例）

# 5. 构建并启动
cd /opt/claude-code-telegram
docker-compose build
docker-compose up -d
```

---

## 目录结构

部署后的目录结构：

```
/opt/claude-code-telegram/
├── claude-code-telegram/      # Telegram Bot 代码
├── claudecode/                # 本地 Bun 实现
├── data/
│   └── bot.db                 # SQLite 数据库（持久化）
├── projects/                  # Claude 工作目录（持久化）
│   └── .gitkeep
├── config/                    # 配置文件（可选）
├── logs/                      # 日志文件（持久化）
├── .env                       # 环境变量
├── Dockerfile
├── docker-compose.yml
deploy.sh
```

### 关键挂载点

| 宿主机路径 | 容器内路径 | 用途 |
|-----------|-----------|------|
| `./data` | `/data` | 数据库存储 |
| `./projects` | `/projects` | 项目工作目录 |
| `./config` | `/app/config` | 配置文件 |
| `./logs` | `/app/logs` | 日志文件 |

---

## 权限问题详解

### 核心问题

在 Docker 容器中运行 Claude Code 时，主要面临以下权限挑战：

1. **文件系统权限** - 容器内外用户 ID 不匹配
2. **工具调用权限** - Bash、Git 等工具是否能正常执行
3. **文件编辑权限** - 创建、修改、删除文件的权限
4. **网络权限** - 访问外部 API

### 解决方案概览

我们的 Dockerfile 采用了以下策略解决权限问题：

```dockerfile
# 1. 创建非 root 用户（安全）
RUN groupadd -r claudebot && useradd -r -g claudebot -m -s /bin/bash claudebot

# 2. 设置目录权限
RUN chown -R claudebot:claudebot /app /data /projects

# 3. 使用非 root 用户运行
USER claudebot
```

---

## 工具调用权限

### 可用的工具

在 Docker 容器中，Claude 可以正常使用以下工具：

| 工具 | 可用性 | 说明 |
|------|--------|------|
| **Read** | ✅ 完全支持 | 读取 `/projects` 目录下的文件 |
| **Write** | ✅ 完全支持 | 创建新文件 |
| **Edit** | ✅ 完全支持 | 修改现有文件 |
| **Bash** | ✅ 完全支持 | 执行 shell 命令 |
| **LS** | ✅ 完全支持 | 列出目录内容 |
| **Glob** | ✅ 完全支持 | 文件匹配 |
| **Grep** | ✅ 完全支持 | 文本搜索 |
| **Git** | ✅ 完全支持 | 版本控制操作 |
| **Task** | ⚠️ 有限支持 | 可能受资源限制 |
| **MCP** | ⚠️ 视配置而定 | 需要额外配置 |

### Bash 工具权限

Bash 命令在容器中以 `claudebot` 用户执行，拥有：

- ✅ 读写 `/projects` 目录
- ✅ 执行已安装的工具（git、vim、curl、wget、jq 等）
- ✅ 临时文件操作（/tmp）
- ❌ root 权限（无法修改系统文件）
- ❌ 访问容器外文件

### 测试工具权限

部署后，在 Telegram 中测试：

```
你：执行 pwd 和 whoami
Bot:  💻 Bash: pwd
      /projects
      💻 Bash: whoami
      claudebot

你：创建测试文件
Bot:  📝 Write: test.txt
      已创建文件

你：查看文件内容
Bot:  📖 Read: test.txt
      [显示内容]

你：删除测试文件
Bot:  💻 Bash: rm test.txt
      已删除
```

---

## 文件编辑写入权限

### 权限配置详解

我们的方案采用了**用户 ID 映射**策略：

```dockerfile
# 容器内用户
USER claudebot  # UID: 999

# 目录权限
RUN chown -R 1000:1000 /data /projects
```

### 为什么这样能工作？

1. **容器内**：`claudebot` 用户拥有 `/projects` 的读写权限
2. **容器外**：宿主机用户（通常是 UID 1000）拥有 `./projects` 的权限
3. **Docker 挂载**：权限通过 UID/GID 传递，不需要用户名匹配

### 验证权限

在宿主机上检查：

```bash
# 查看 projects 目录权限
ls -la /opt/claude-code-telegram/projects/

# 应该显示：
# drwxr-xr-x 2 1000 1000 4096 Jan 10 10:00 .
# drwxr-xr-x 6 root root 4096 Jan 10 10:00 ..
```

在容器中检查：

```bash
# 进入容器
docker exec -it claude-telegram-bot /bin/bash

# 检查权限
ls -la /projects
whoami  # 输出: claudebot
touch /projects/test.txt  # 应该成功
rm /projects/test.txt     # 应该成功
```

### 权限问题排查

如果遇到权限错误：

```
❌ 错误：Permission denied when writing file
```

**解决方案 1：检查 UID 映射**

```bash
# 在宿主机上查看当前用户 ID
id -u  # 输出: 1000

# 修改目录权限为当前用户
sudo chown -R $(id -u):$(id -g) /opt/claude-code-telegram/projects
```

**解决方案 2：使用 named volumes（不推荐用于开发）**

```yaml
# docker-compose.yml
volumes:
  - projects-data:/projects

volumes:
  projects-data:
```

**解决方案 3：特权模式（不推荐，有安全风险）**

```yaml
# docker-compose.yml
services:
  claude-telegram-bot:
    privileged: true
```

---

## 故障排查

### 问题 1：容器无法启动

**症状**：
```
ERROR: for claude-telegram-bot  Cannot start service
```

**排查步骤**：

```bash
# 查看详细错误
docker-compose logs

# 检查环境变量
 cat /opt/claude-code-telegram/.env | grep TELEGRAM_BOT_TOKEN

# 手动运行查看错误
docker-compose up  # 不加 -d，前台运行
```

### 问题 2：无法写入文件

**症状**：Bot 提示 Permission denied

**解决方案**：

```bash
# 1. 停止容器
docker-compose down

# 2. 修复权限
sudo chown -R 1000:1000 /opt/claude-code-telegram/projects
sudo chmod -R 755 /opt/claude-code-telegram/projects

# 3. 重启
docker-compose up -d
```

### 问题 3：数据库锁定

**症状**：
```
sqlite3.OperationalError: database is locked
```

**解决方案**：

```bash
# 检查是否有多个进程访问数据库
docker exec claude-telegram-bot ps aux | grep python

# 重启容器
docker-compose restart
```

### 问题 4：时区问题

**解决方案**：

```dockerfile
# Dockerfile 中添加
RUN ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime
echo "Asia/Shanghai" > /etc/timezone
```

或在 docker-compose.yml 中：

```yaml
environment:
  - TZ=Asia/Shanghai
```

### 问题 5：网络访问失败

**症状**：无法访问 API

**排查**：

```bash
# 测试网络
docker exec claude-telegram-bot curl -I https://api.anthropic.com

# 检查 DNS
docker exec claude-telegram-bot nslookup api.anthropic.com
```

---

## 安全建议

### 1. 使用非 root 用户

✅ 已实现：Dockerfile 中使用 `USER claudebot`

### 2. 限制容器资源

```yaml
# docker-compose.yml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 2G
    reservations:
      cpus: '0.5'
      memory: 512M
```

### 3. 只读挂载（可选）

```yaml
volumes:
  - ./config:/app/config:ro  # 只读
```

### 4. 禁用特权模式

❌ 不要添加：
```yaml
privileged: true
```

### 5. 定期更新

```bash
# 更新镜像
docker-compose pull
docker-compose up -d

# 清理旧镜像
docker image prune -f
```

### 6. 备份数据

```bash
# 创建备份脚本
#!/bin/bash
BACKUP_DIR="/backup/claude-bot/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"
cp -r /opt/claude-code-telegram/data "$BACKUP_DIR/"
cp -r /opt/claude-code-telegram/projects "$BACKUP_DIR/"
echo "Backup completed: $BACKUP_DIR"
```

---

## 高级配置

### 使用外部数据库

如果使用 PostgreSQL 替代 SQLite：

```yaml
# docker-compose.yml
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: claudebot
      POSTGRES_PASSWORD: secretpassword
      POSTGRES_DB: claudebot
    volumes:
      - postgres-data:/var/lib/postgresql/data
    
  bot:
    # ... 其他配置
    environment:
      - DATABASE_URL=postgresql://claudebot:secretpassword@db:5432/claudebot
    depends_on:
      - db

volumes:
  postgres-data:
```

### 使用反向代理（Nginx）

如果需要 Webhook 模式：

```nginx
# /etc/nginx/sites-available/claude-bot
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    location /webhook {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 总结

### ✅ Docker 中工具调用完全支持

- 文件读写 ✅
- Bash 命令 ✅
- Git 操作 ✅
- 网络访问 ✅

### ✅ 权限问题已解决

- 使用非 root 用户运行
- 正确的 UID/GID 映射
- 持久化目录正确挂载

### 📋 检查清单

部署前请确认：

- [ ] Docker 和 Docker Compose 已安装
- [ ] `.env` 文件已配置（TELEGRAM_BOT_TOKEN、ANTHROPIC_API_KEY）
- [ ] 端口未被占用（如果使用 API 服务器）
- [ ] 磁盘空间充足（至少 5GB 可用）
- [ ] 已配置防火墙（如需要）

---

如有其他问题，请查看日志：

```bash
cd /opt/claude-code-telegram
docker-compose logs -f
```

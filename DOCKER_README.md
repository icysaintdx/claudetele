# Docker 部署总结

## 📦 文件说明

部署到 Linux Docker 所需的文件：

| 文件 | 用途 |
|------|------|
| `Dockerfile` | Docker 镜像构建文件 |
| `docker-compose.yml` | Docker Compose 配置文件 |
| `deploy.sh` | 完整部署脚本（推荐） |
| `deploy-quick.sh` | 快速部署脚本 |
| `DOCKER_DEPLOY.md` | 详细部署文档 |

---

## 🚀 快速开始

### 方式 1：使用部署脚本（推荐）

```bash
# 1. 将文件上传到服务器
scp -r claude-code-telegram claudecode Dockerfile docker-compose.yml deploy.sh root@your-server:/root/

# 2. SSH 登录服务器
ssh root@your-server

# 3. 运行部署脚本
cd /root
chmod +x deploy.sh
./deploy.sh

# 4. 编辑环境变量
nano /opt/claude-code-telegram/.env

# 5. 启动服务
cd /opt/claude-code-telegram
docker-compose up -d
```

### 方式 2：快速部署

```bash
chmod +x deploy-quick.sh
./deploy-quick.sh /opt/claude-bot
```

### 方式 3：手动部署

```bash
# 安装 Docker
curl -fsSL https://get.docker.com | sh

# 创建目录
mkdir -p /opt/claude-bot/{data,projects}
cp -r claude-code-telegram claudecode Dockerfile docker-compose.yml /opt/claude-bot/

# 创建 .env 文件
cat > /opt/claude-bot/.env << 'EOF'
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_BOT_USERNAME=your_bot
ANTHROPIC_API_KEY=your_key
EOF

# 启动
cd /opt/claude-bot
docker-compose up -d
```

---

## 🔐 权限问题解答

### 工具调用是否有权限？

✅ **完全支持！** Docker 容器中 Claude 可以正常使用：

- ✅ 读写文件（Read/Write/Edit）
- ✅ 执行 Bash 命令
- ✅ Git 操作（add/commit/push/pull）
- ✅ 创建、删除、修改文件
- ✅ 安装和使用工具（curl、wget、jq 等）

### 文件编辑写入是否有权限？

✅ **有权限！** 我们的方案：

1. 创建专用用户 `claudebot`（非 root，安全）
2. `/projects` 目录挂载到宿主机，数据持久化
3. 正确的用户 ID 映射，权限一致
4. 容器内外都能正常读写

### 用户权限映射

```
容器内: claudebot (UID 1000)  <--->  宿主机: 普通用户 (UID 1000)
              ↓                              ↓
         /projects (读写)              ./projects (读写)
```

---

## 📂 目录挂载

```yaml
volumes:
  - ./data:/data           # 数据库持久化
  - ./projects:/projects   # 项目工作目录（Claude 操作的目录）
  - ./config:/app/config   # 配置文件（只读）
  - ./logs:/app/logs       # 日志文件
```

**重要**：`/projects` 是 Claude 的工作目录，所有文件操作都在这里。

---

## 🔧 常用命令

```bash
# 查看日志
docker-compose logs -f

# 查看最后 100 行
docker-compose logs --tail 100

# 重启服务
docker-compose restart

# 停止服务
docker-compose down

# 进入容器
docker exec -it claude-telegram-bot /bin/bash

# 查看资源使用
docker stats claude-telegram-bot

# 更新镜像
docker-compose pull
docker-compose build --no-cache
docker-compose up -d

# 备份数据
cp -r data data-backup-$(date +%Y%m%d)
cp -r projects projects-backup-$(date +%Y%m%d)
```

---

## ⚠️ 注意事项

1. **环境变量**：部署后必须编辑 `.env` 文件填入真实的 Token 和 API Key
2. **防火墙**：如果使用 Webhook 模式，需要开放相应端口
3. **磁盘空间**：确保有足够的空间用于项目和数据库
4. **权限修复**：如果遇到权限问题，运行：
   ```bash
   sudo chown -R 1000:1000 /opt/claude-code-telegram/projects
   ```

---

## 📚 详细文档

- 完整部署指南：`DOCKER_DEPLOY.md`
- 持久化上下文：`claude-code-telegram/docs/persistent-context.md`
- 本地 Bun 配置：`claude-code-telegram/docs/local-bun-setup.md`

---

## 🐛 故障排查

### 问题：Permission denied

```bash
# 解决方案
sudo chown -R $(id -u):$(id -g) ./projects
sudo chmod -R 755 ./projects
docker-compose restart
```

### 问题：容器无法启动

```bash
# 查看日志
docker-compose logs

# 检查环境变量
 cat .env | grep TELEGRAM_BOT_TOKEN
```

### 问题：工具调用失败

```bash
# 进入容器测试
docker exec -it claude-telegram-bot /bin/bash
whoami  # 应该是 claudebot
touch /projects/test.txt  # 测试写入权限
rm /projects/test.txt
```

---

## ✅ 部署检查清单

- [ ] 服务器有 Docker 和 Docker Compose
- [ ] 上传了所有必需文件
- [ ] 编辑了 `.env` 文件，填入 Token 和 API Key
- [ ] 创建了 `data` 和 `projects` 目录
- [ ] 运行了 `docker-compose up -d`
- [ ] 查看了日志，确认无错误
- [ ] 在 Telegram 中测试了 Bot
- [ ] 测试了文件读写功能
- [ ] （可选）配置了 systemd 自动启动

---

有任何问题，请查看详细文档 `DOCKER_DEPLOY.md` 或检查日志！

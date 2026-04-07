# 方案 B：使用本地 Bun 实现的 Claude Code

本文档说明如何配置 Telegram Bot 使用你的本地 Bun 实现的 Claude Code（claude-code-local），而不是官方的 Claude CLI。

## 概述

默认情况下，claude-code-telegram 使用官方的 `claude-agent-sdk` 与 Claude Code CLI 通信。方案 B 允许你使用自己手搓的 Bun 实现来替代官方 CLI。

### 架构对比

**方案 A（默认）：**
```
Telegram Bot -> claude-agent-sdk -> 官方 Claude CLI
```

**方案 B（本地实现）：**
```
Telegram Bot -> LocalBunManager -> bun run cli.tsx -p "prompt"
```

## 配置步骤

### 1. 确保本地项目可运行

首先确保你的 claude-code-local 项目可以正常运行：

```bash
cd D:\claudecode

# 测试本地实现
bun --env-file=.env ./src/entrypoints/cli.tsx -p "Hello, are you working?"
```

如果看到正常输出，说明本地实现可用。

### 2. 配置 Telegram Bot 使用本地实现

编辑 `claude-code-telegram/.env`：

```bash
cd D:\claudecode\claude-code-telegram
cp .env.example .env
```

关键配置项：

```env
# === 基础配置（与方案 A 相同）===
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_BOT_USERNAME=your_bot_username
APPROVED_DIRECTORY=D:\claudecode\projects
ALLOWED_USERS=123456789

# === 关键：启用本地 Bun 实现 ===
USE_LOCAL_BUN=true
LOCAL_BUN_PROJECT_PATH=D:\claudecode

# === API 配置（本地实现仍然需要）===
# 你的 Bun 实现需要 API Key 来调用 LLM
ANTHROPIC_API_KEY=your-api-key
# 或者使用自定义端点（如 MiniMax）
# ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic

# === 其他配置 ===
CLAUDE_TIMEOUT_SECONDS=300
AGENTIC_MODE=true
VERBOSE_LEVEL=1
```

### 3. 运行 Bot

```bash
# 使用 Poetry
poetry run python -m src.main

# 或者使用 Make
make run-debug
```

## 目录结构要求

项目会自动检测本地 Bun 项目的路径。检测逻辑：

1. **环境变量**：检查 `CLAUDE_LOCAL_PROJECT_PATH`
2. **配置项**：检查 `LOCAL_BUN_PROJECT_PATH`
3. **自动检测**：尝试以下相对路径：
   - `../claude-code-local`
   - `../claudecode`
   - `../../claude-code-local`
   - `../../claudecode`
4. **当前目录**：检查当前工作目录

检测成功的标志是找到 `src/entrypoints/cli.tsx` 文件。

## 技术实现细节

### LocalBunManager 工作原理

`LocalBunManager` 类替代了 `ClaudeSDKManager`，通过 subprocess 调用 Bun：

```python
cmd = [
    "bun",
    "--env-file=.env",
    "./src/entrypoints/cli.tsx",
    "-p",  # Print/headless mode
    prompt,
]
```

### 支持的特性

| 特性 | 本地实现支持 | 说明 |
|------|-------------|------|
| 基本对话 | ✅ | 完全支持 |
| 流式输出 | ✅ | 实时传输到 Telegram |
| 图片输入 | ⚠️ | 提示用户本地实现可能不支持 |
| 会话恢复 | ⚠️ | 使用伪会话 ID，不完全支持 |
| 成本追踪 | ❌ | 本地实现不返回成本 |
| 工具调用追踪 | ✅ | 从输出中提取 |

### 环境变量传递

以下环境变量会自动传递给 Bun 进程：

- `ANTHROPIC_API_KEY` - API 认证
- `ANTHROPIC_MODEL` - 模型选择
- `API_TIMEOUT_MS` - 超时设置
- `DISABLE_TELEMETRY=1` - 禁用遥测
- `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` - 禁用非必要流量

## 故障排查

### Bot 启动时报错 "Could not find local Claude Code project"

**原因**：无法找到有效的 Bun 项目路径

**解决**：
1. 确认 `LOCAL_BUN_PROJECT_PATH` 设置正确
2. 确认路径下存在 `src/entrypoints/cli.tsx`
3. 手动设置环境变量：
   ```powershell
   $env:CLAUDE_LOCAL_PROJECT_PATH = "D:\claudecode"
   ```

### 命令执行超时

**原因**：本地实现响应慢或陷入循环

**解决**：
1. 增加超时时间：
   ```env
   CLAUDE_TIMEOUT_SECONDS=600
   ```
2. 在本地测试中先验证命令：
   ```bash
   bun --env-file=.env ./src/entrypoints/cli.tsx -p "复杂命令"
   ```

### 输出格式不正确

**原因**：本地实现的输出格式与预期不符

**解决**：
1. 检查本地实现的 `-p` 模式输出是否纯文本
2. 确保没有额外的日志信息污染 stdout
3. 在 `local_bun_integration.py` 中调整 `_extract_tools_from_output` 的解析逻辑

### Windows 路径问题

**原因**：Windows 路径分隔符或空格问题

**解决**：
1. 使用原始字符串或双反斜杠：
   ```env
   LOCAL_BUN_PROJECT_PATH=D:\\claudecode
   # 或
   LOCAL_BUN_PROJECT_PATH="D:\\claudecode"
   ```
2. 确保路径中没有特殊字符

## 与官方 CLI 的对比

| 方面 | 官方 CLI | 本地 Bun 实现 |
|------|----------|--------------|
| **安装** | `npm install -g @anthropic-ai/claude-code` | `git clone` + `bun install` |
| **认证** | `claude auth login` 或 API Key | 仅 API Key |
| **会话管理** | 完整的会话恢复 | 有限的伪会话支持 |
| **多模态** | 完整的图片支持 | 取决于实现 |
| **自定义** | 有限 | 完全可控 |
| **成本追踪** | 准确 | 不支持 |
| **MCP 支持** | 完整 | 取决于实现 |

## 切换回官方实现

如果需要切换回官方 Claude CLI：

```env
# 关闭本地 Bun 模式
USE_LOCAL_BUN=false

# 确保官方 CLI 已安装并认证
# claude auth login
```

## 进阶：混合使用

你可以通过设置多个 Bot 实例来同时使用两种方式：

1. **实例 A**：`USE_LOCAL_BUN=true` - 使用你的定制实现
2. **实例 B**：`USE_LOCAL_BUN=false` - 使用官方 CLI

每个实例使用不同的 Telegram Bot Token，根据需求选择使用。

## 开发建议

### 如果你想增强本地实现

当前 `LocalBunManager` 通过 `-p` 参数调用你的实现。你可以扩展你的 Bun 项目以支持更多功能：

1. **会话持久化**：实现基于文件的会话存储
2. **流式输出**：使用 SSE 或 WebSocket 实时传输
3. **成本估算**：在输出中添加 token 使用统计

### 调试技巧

启用详细日志查看实际调用的命令：

```env
LOG_LEVEL=DEBUG
DEBUG=true
```

查看日志中的：
- "Starting local Bun Claude command" - 确认进入本地模式
- "Building CLI command" - 查看完整命令
- "Local Claude command completed" - 查看执行结果

## 总结

方案 B 让你能够：
- ✅ 完全控制 Claude Code 的实现
- ✅ 接入任意兼容 Anthropic API 的端点
- ✅ 自定义工具和行为
- ⚠️ 放弃部分官方功能（会话恢复、成本追踪等）
- ⚠️ 需要自行维护代码

适合有定制需求、想要深度控制的技术用户。

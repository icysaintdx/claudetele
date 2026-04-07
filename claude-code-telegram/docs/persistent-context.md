# 持久化对话上下文功能

## 概述

现在 Telegram Bot 支持**永久保存对话上下文**！这意味着：

✅ **自动记住对话历史** - 每条消息都会保存在 SQLite 数据库中  
✅ **跨消息保持上下文** - 除非你说 `/new`，否则上下文一直保留  
✅ **重启 Bot 也不会丢失** - 数据存储在数据库中  
✅ **随时清除历史** - 使用 `/new` 命令开始全新对话

---

## 工作原理

### 传统方式（无持久化）

```
用户: 查看文件
Bot:  [执行 LS]
用户: 编辑最后一个文件  ← ❌ Bot 不知道"最后一个文件"是哪个
```

### 新方式（有持久化）

```
用户: 查看文件
Bot:  [执行 LS] 发现 main.py, utils.py, config.py
用户: 编辑最后一个文件  ← ✅ Bot 从上下文中知道是 config.py
Bot:  [执行 Edit: config.py]
```

---

## 使用方法

### 正常对话（自动保持上下文）

直接在 Telegram 里连续对话即可，Bot 会自动记住之前的交流：

```
你：创建一个新项目
Bot：好的，我来创建项目结构...

你：添加一个 README  ← Bot 知道要在新项目里添加
Bot：已添加 README.md

你：现在提交到 git  ← Bot 知道要提交刚才的更改
Bot：已执行 git add . && git commit...
```

### 开始新会话（清除历史）

当你想清除所有上下文，开始全新对话时：

```
/new
```

或者点击菜单中的 **"🆕 New Session"** 按钮。

这会：
- ✅ 清除对话历史
- ✅ 清除会话状态
- ✅ 保留文件更改（只清内存，不动文件）

---

## 技术实现

### 数据存储

对话历史存储在 SQLite 数据库的 `conversation_messages` 表中：

```sql
CREATE TABLE conversation_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,        -- 'user' 或 'assistant'
    content TEXT NOT NULL,     -- 消息内容
    timestamp TEXT NOT NULL,   -- 时间戳
    metadata TEXT              -- 额外信息（工作目录等）
);
```

### 上下文传递

当继续会话时，Bot 会把历史消息**拼接到 Prompt 中**：

```
=== CONVERSATION CONTEXT ===
The following is the conversation history. Please respond to the last message.

User: 创建一个新项目
Assistant: 好的，我来创建项目结构...
User: 添加一个 README
Assistant: 已添加 README.md

=== NEW MESSAGE ===
User: 现在提交到 git

Assistant:
```

### 上下文长度限制

为了防止超过 LLM 的上下文窗口，默认只保留**最近 50 条消息**。可以通过配置调整：

```python
# 在 local_bun_integration.py 中修改
max_context_messages = 50  # 改为需要的数量
```

---

## 配置选项

### 环境变量

```env
# 数据库位置（对话历史存储在这里）
DATABASE_URL=sqlite:///data/bot.db

# 会话超时时间（小时）
SESSION_TIMEOUT_HOURS=72

# 每用户最大会话数
MAX_SESSIONS_PER_USER=10
```

### 代码配置

```python
# 最大上下文消息数（防止 Token 超限）
max_context_messages = 50

# 是否启用消息存储（默认启用）
use_message_storage = True
```

---

## 常见问题

### Q: 对话历史会保存多久？

**A:** 永久保存，直到：
- 用户执行 `/new` 命令
- 会话超时（默认 72 小时无活动）
- 手动删除数据库文件

### Q: 可以查看历史记录吗？

**A:** 目前只能通过直接查询数据库查看：

```bash
sqlite3 data/bot.db "SELECT * FROM conversation_messages WHERE session_id='xxx' ORDER BY timestamp;"
```

### Q: 切换项目会保留上下文吗？

**A:** 每个项目（目录）有独立的上下文。使用 `/cd` 或 `/repo` 切换项目时：
- ✅ 自动恢复该项目的上下文
- ✅ 原项目的上下文仍然保留

### Q: 如何导出对话历史？

**A:** 目前可以通过数据库导出：

```bash
# 导出为 SQL
sqlite3 data/bot.db ".dump conversation_messages" > history.sql

# 导出为 CSV
sqlite3 -header -csv data/bot.db "SELECT * FROM conversation_messages;" > history.csv
```

### Q: 上下文太长会影响性能吗？

**A:** 会，但已做优化：
- 只保留最近 50 条消息
- 超长消息会被截断
- 可以调整 `max_context_messages` 参数

---

## 故障排查

### 问题：上下文没有保持

**检查：**
1. 确认使用了 `USE_LOCAL_BUN=true`
2. 检查日志中是否有 "Message stored" 字样
3. 查看数据库是否有数据：`sqlite3 data/bot.db "SELECT COUNT(*) FROM conversation_messages;"`

### 问题：/new 没有清除历史

**检查：**
1. 确认 Bot 已重启（加载了新代码）
2. 检查日志中是否有 "Cleared conversation history" 字样
3. 手动检查数据库：`sqlite3 data/bot.db "SELECT * FROM conversation_messages WHERE session_id='xxx';"`

---

## 文件变更

实现此功能修改了以下文件：

1. **新增** `src/storage/message_storage.py` - 消息历史存储
2. **修改** `src/claude/local_bun_integration.py` - 支持上下文拼接
3. **修改** `src/claude/facade.py` - 添加 message_storage 支持
4. **修改** `src/main.py` - 初始化 message_storage
5. **修改** `src/bot/handlers/command.py` - /new 命令清除历史
6. **修改** `src/storage/__init__.py` - 导出 MessageHistoryStorage

---

## 未来增强

可能的改进方向：

- 📤 导出对话为 Markdown/HTML
- 🔍 搜索历史对话
- 📊 对话统计和可视化
- 🧹 自动清理旧对话
- 💾 对话分支（类似 Git 分支）

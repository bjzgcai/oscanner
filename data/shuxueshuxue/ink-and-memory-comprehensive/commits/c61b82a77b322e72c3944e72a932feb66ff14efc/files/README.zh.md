# Ink & Memory · 中文 | [English](README.md)

Ink & Memory 是一款受《极乐迪斯科》启发的写作工作室：每个句子都会触发内心声音的实时评论。它支持自动保存、日历与时间线回顾、好友时间线，以及按用户时区显示。整套体验支持中英文。

![Writing area](assets/writing-area.png)

---

## 能做什么
- **双语写作**：笔记、本地高亮、标题、语音评论支持中英文，随输入自动切换。
- **听内心合唱团**：十三个迪斯科式声音实时评论，各有颜色、图标、人格。
- **信任自动保存**：手动“保存今天”和 3 秒自动保存共用同一逻辑，`editor_state.createdAt` 始终存在，可从日历或时间线恢复。
- **回看每日**：日历与时间线复用同一分组数据，标题、图片、时间戳一致；点击某天加载对应会话。
- **好友对比**：可固定好友时间线，空档会提示引导卡片。
- **本地时区显示**：时间戳以 UTC 存储，前端用浏览器时区转换；后端也记录首选时区。

---

## 声音阵容
十三个《极乐迪斯科》原型：Logic、Empathy、Inland Empire、Volition、Drama、Authority、Half Light、Shivers、Composure、Encyclopedia、Conceptualization、Suggestion、Electrochemistry。每个声线独立记录评论、避免重复，并按当前写作语言回应。

---

## 架构速览

### 前端（React + TypeScript）
- TipTap 编辑器，自定义高亮和声线覆盖层。
- 3 秒自动保存与手动保存共用流程。
- 共享的会话分组工具（`src/utils/sessionGrouping.ts`）驱动日历弹窗与时间线。
- 浏览器时区检测同步到后端偏好。

### 后端（FastAPI + PolyCLI）
- 有状态分析器：密度规则、去重、情绪提示。
- 时间线图片定时器（未来按用户调度），基于 PolyCLI 会话。
- SQLite 持久化，进程启动强制 TZ=UTC。
- 控制台 + 会话注册表用于调试和 PolyCLI 试验。

---

## 本地运行

### 先决条件
- Python 3.11+
- Node.js 18+
- [uv](https://github.com/astral-sh/uv)（Python 包管理）

### 后端
```bash
cd backend
uv venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv pip install -e ../PolyCLI
uv pip install beautifulsoup4 requests 'httpx[socks]'

cat > models.json <<'EOC'
{
  "models": {
    "gpt-4o-dou": {
      "endpoint": "https://api.example.com/v1",
      "api_key": "your-api-key",
      "model": "openai/chatgpt-4o-latest"
    }
  }
}
EOC

python server.py
```
默认运行在 `http://localhost:8765`。

### 前端
```bash
cd frontend
npm install
npm run dev
```
默认运行在 `http://localhost:5173`。

---

## 部署提示（概要）
- 前端：`npm run build` 输出 `frontend/dist/`，同步到 `/var/www/lexicalmathical.com/ink-and-memory/`，由 Nginx 提供静态文件。
- 后端：Docker 镜像（GHCR）。运行时挂载：
  - `/root/ink-and-memory/backend/data:/app/data`（SQLite）
  - `/root/ink-and-memory/backend/models.json:/app/models.json:ro`（模型与 API Key）
- Nginx：静态 `/ink-and-memory/`；反代 `/ink-and-memory/api`、`/ink-and-memory/polycli` 到 `127.0.0.1:8765`。

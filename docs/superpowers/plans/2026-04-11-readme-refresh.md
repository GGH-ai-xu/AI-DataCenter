# README Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite `README.md` so it matches the current codebase, serving both first-time readers and developers who need accurate startup and architecture context.

**Architecture:** Keep the change isolated to documentation. Rebuild `README.md` around the current routed product surface, actual backend/agent/runtime modules, and the real Windows-first startup flow. Verify with lightweight Windows commands that the documented structure still matches a buildable repository.

**Tech Stack:** Markdown, FastAPI backend, Vue 3 + Vite frontend, Python agent, Windows PowerShell launch scripts

---

### Task 1: Rebuild README Structure Around Current Product Surface

**Files:**
- Modify: `README.md`
- Reference: `frontend/src/main.js`
- Reference: `frontend/src/views/AIWorkspaceLayout.vue`
- Reference: `frontend/src/views/AIAssistant.vue`
- Reference: `frontend/src/views/AIGraphWorkspace.vue`
- Reference: `frontend/src/views/ClusterJobs.vue`
- Reference: `backend/app/main.py`
- Reference: `server-agent/main.py`
- Reference: `backend/.env.example`
- Reference: `scripts/start-dev.ps1`

- [ ] **Step 1: Rewrite the README title, project positioning, and core capability overview**

Replace the opening block with a concise overview covering:

```md
# AI DataCenter

AI DataCenter 是一个面向共享 GPU / 智算资源场景的治理平台。它不是单纯的监控看板，而是围绕“平台登录、导入接入、运行时治理、AI 工作台、图谱分析、集群控制”组织的一套完整控制台。

## 核心能力

- 平台登录与用户隔离 workspace
- 独立导入层：本机 Agent、远程 Agent、SSH Linux
- 控制台六个主入口：总览、治理、能耗、观察、告警、智能
- AI 双工作台：智能工作台、图谱工作台
- goal runtime、审批流、会话事件与流式问答
- 集群控制：queue、job、allocation、自动调和
```

- [ ] **Step 2: Add a workflow section and update the repository structure section**

Insert a “典型工作流” section and replace the old directory description with:

```md
## 典型工作流

1. 登录平台。
2. 进入独立导入层，选择本机 Agent、远程 Agent 或 SSH Linux。
3. 扫描目标机器并确认 CPU / GPU 资源。
4. 勾选本次纳入治理的 GPU，进入控制台。
5. 在治理、能耗、观察、告警、智能或图谱工作台中继续操作。

## 目录结构

```text
backend/        FastAPI 后端、平台身份、导入层、控制面、AI/图谱/集群 API
server-agent/   部署在目标机上的采集与执行 Agent，提供 GPU / 任务 / runtime 接口
frontend/       Vue 3 + Vite 控制台，包含导入层、治理台、AI 工作台、图谱工作台
desktop-shell/  Electron 桌面壳
scripts/        Windows 开发、Neo4j、自启动与打包脚本
tests/          仓库级结构与回归测试
runtime/        本地运行时数据、主密钥、导入上下文与平台状态，禁止提交
```
```

- [ ] **Step 3: Replace the startup and dependency sections with Windows-first instructions**

Rewrite the startup section so it explicitly documents:

```md
## 快速开始

推荐在 Windows 开发机上使用仓库自带脚本：

```powershell
.\install-deps.bat
.\start-dev.bat
```

`start-dev.bat` / `scripts/start-dev.ps1` 会自动：

- 检查 `.venv` 和 `frontend/node_modules`
- 启动本机 `server-agent`
- 启动 FastAPI backend
- 启动 Vite frontend
- 生成或复用 `runtime/` 下的本地主密钥
- 在检测到脚本存在时尝试准备本地 Neo4j
```

Then add a “手动启动与关键依赖” section covering:

```md
## 手动启动与关键依赖

- Backend 手动启动前需要设置 `GPU_GOV_MASTER_KEY`
- `backend/.env.example` 提供 `LLM_*` 和 `NEO4J_*` 示例配置
- SSH Linux 模式要求目标机可 SSH 登录、可执行 `nvidia-smi`，必要时具备 `sudo`
- 本机 Agent 即使在无 NVIDIA GPU 的开发机上启动，也会以“无真实 GPU”告警形式显式暴露状态
```

- [ ] **Step 4: Add current runtime capabilities, verification, and security sections**

Append three concise sections with these facts:

```md
## 当前实现中的关键运行能力

- goal runtime 会把自然语言请求路由到聊天或执行链路，并维护会话上下文
- 智能工作台支持会话历史、审批、事件回放与流式响应
- 图谱工作台支持知识入图、图谱浏览、图谱问答与策略生成
- 集群控制台支持队列、作业、allocation、节点排空和自动调和
- control plane 统一承载人工操作与 Agent capability 调用

## 开发校验

```powershell
python -m compileall .\backend\app .\server-agent
python -m unittest discover -s .\tests -p "test_*.py"

cd .\frontend
npm test
npm run build
```

## 安全与运行时数据

以下内容只应保留在本地，不应提交到公开仓库：

- `runtime/`
- `backend/data/`
- `.env`
- 任意真实 API Key、SSH 凭据、数据库、日志与构建产物
```

### Task 2: Verify the Documentation Against the Current Repository

**Files:**
- Verify: `README.md`

- [ ] **Step 1: Run Python compileall from Windows**

Run:

```bash
cmd.exe /d /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m compileall backend\app server-agent"
```

Expected: exit code `0`, with Python bytecode compilation messages and no traceback.

- [ ] **Step 2: Run the frontend production build from Windows**

Run:

```bash
cmd.exe /d /c "cd /d E:\Code\AI-DataCenter\frontend && npm.cmd run build"
```

Expected: exit code `0`, with a successful Vite build summary and no fatal error.

- [ ] **Step 3: Review the diff to ensure only README and planning/spec docs changed**

Run:

```bash
git diff -- README.md docs/superpowers/specs/2026-04-11-readme-refresh-design.md docs/superpowers/plans/2026-04-11-readme-refresh.md
```

Expected: diff only contains the README rewrite and the associated spec/plan documents for this task.

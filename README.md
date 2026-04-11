# AI DataCenter

AI DataCenter 是一个面向共享 GPU / 智算资源场景的治理平台。它不是单纯的监控看板，而是围绕“平台登录、导入接入、运行时治理、AI 工作台、图谱分析、集群控制”组织的一套完整控制台。

## 项目定位

当前代码库已经落地了这几类核心能力：

- 平台登录与用户隔离 workspace
- 独立导入层，支持本机 Agent、远程 Agent、SSH Linux 三种接入方式
- 控制台六个主入口：总览、治理、能耗、观察、告警、智能
- AI 双工作台：智能工作台、图谱工作台
- goal runtime、审批流、会话事件、流式问答
- 集群控制：queue、job、allocation、节点排空、自动调和
- 统一 control plane，让人工操作和 Agent capability 走同一条底层控制链

项目的基本使用方式不是“直接打开控制台”，而是：

1. 先登录平台。
2. 进入独立导入层。
3. 扫描目标机器并选择本次纳入治理的 GPU。
4. 再进入控制台做治理、复盘、AI 问答或图谱分析。

控制台默认只作用于本次导入范围，不承担连接切换逻辑。

## 当前产品结构

### 平台与导入层

- 平台启动后会自动确保默认管理员存在。
- 默认管理员用户名为 `admin`。
- 默认密码来自 `GPU_GOV_DEFAULT_ADMIN_PASSWORD`，未配置时为 `admin123456`。
- 登录后先进入独立导入层，而不是直接进入控制台。
- 导入层支持三种来源：
  - 本机 Agent：适合当前机器本地部署 `server-agent`
  - 远程 Agent：适合目标机器已经运行 `server-agent`
  - SSH Linux：适合目标机不运行 agent，由平台通过 SSH 读取 Linux 与 NVIDIA 数据
- 已保存主机会按用户隔离保存；管理员可查看全部主机记录，普通用户只能查看自己的记录。

### 控制台主入口

当前前端主入口与职责大致如下：

| 入口 | 职责 |
| --- | --- |
| 总览 | 当前导入范围的健康、资源和巡检总览 |
| 治理 | 即时处置、策略治理、集群控制、治理复盘 |
| 能耗 | 节能分析、功耗预算、能效复盘 |
| 观察 | 监控观察、运行过程与画像信息 |
| 告警 | 风险台、实时告警、归档与确认 |
| 智能 | AI 助手入口，承载对话和执行工作流 |

### AI 双工作台

智能页当前包含两个并列工作台：

- `智能工作台`
  - 面向自然语言对话、审批、执行和事件回放
  - 维护会话历史，并支持流式响应
- `图谱工作台`
  - 支持知识入图、图谱浏览、图谱问答、策略生成
  - 可把图谱策略结果继续送回智能工作台执行

### 集群控制与统一控制面

当前代码库已经把一部分治理能力收敛到统一控制面和集群控制链路中：

- control plane 负责统一承载人工操作与 Agent capability 调用
- cluster control 负责 queue、job、allocation、reservation、checkpoint、reconcile 等对象
- server-agent 暴露 runtime reservation、launch、checkpoint、restore 等接口

这意味着系统不再只是“对已有进程做治理”，而是在朝“作业与资源对象化控制”推进。

## 典型工作流

### 1. 平台登录与导入

1. 启动平台。
2. 使用管理员或已有账号登录。
3. 在导入层选择本机 Agent、远程 Agent 或 SSH Linux。
4. 扫描目标机器。
5. 确认 CPU / GPU 信息，并勾选本次纳入治理的 GPU。
6. 进入控制台。

### 2. 控制台治理

进入控制台后，可以按场景分别进入：

- `治理`
  - 即时处置正在运行的任务
  - 配置策略治理动作
  - 在集群控制台查看 queue / job / allocation
  - 在治理复盘页查看命令账本与执行结果
- `能耗`
  - 查看能耗分析、预算治理和节能建议
- `观察`
  - 查看运行状态、过程画像和资源视图
- `告警`
  - 查看风险、确认异常、做归档复盘
- `智能`
  - 用自然语言发起问答或执行请求
  - 在审批模式下确认高风险动作

### 3. AI 与图谱联动

1. 在 `图谱工作台` 生成图谱策略或查询结果。
2. 将生成的控制提示送入 `智能工作台`。
3. 由 goal runtime 判断走聊天链路还是执行链路。
4. 如涉及真实操作，在低权限模式下进入审批。
5. 在同一会话里继续追问、补充限制或复盘结果。

## 目录结构

```text
backend/        FastAPI 后端、平台身份、导入层、控制面、AI/图谱/集群 API
server-agent/   部署在目标机上的采集与执行 Agent，提供 GPU / 任务 / runtime 接口
frontend/       Vue 3 + Vite 控制台，包含导入层、治理台、AI 工作台、图谱工作台
desktop-shell/  Electron 桌面壳
scripts/        Windows 开发、自启动、本地 Neo4j、打包相关脚本
tests/          仓库级结构与回归测试
runtime/        本地运行时数据、主密钥、导入上下文与平台状态，禁止提交
```

## 快速开始

推荐在 Windows 开发机上直接使用仓库自带脚本：

```powershell
.\install-deps.bat
.\start-dev.bat
```

`start-dev.bat` 会调用 `scripts/start-dev.ps1`，并自动完成这些动作：

- 检查 `.venv` 和 `frontend/node_modules`
- 启动本机 `server-agent`
- 启动 FastAPI backend
- 启动 Vite frontend
- 为平台生成或复用本地主密钥
- 在检测到脚本存在时尝试准备本地 Neo4j
- 自动分配本次开发会话的 agent / backend / frontend 端口

启动完成后，打开启动器打印的 Frontend URL 即可。

## 手动启动与关键依赖

如果不使用 `start-dev.bat`，可以分别启动各服务。

### 1. 启动本机 Agent

```powershell
cd .\server-agent
python .\main.py
```

说明：

- `server-agent` 是部署在目标机上的采集与执行进程。
- 如果当前机器不是 NVIDIA 主机，Agent 会显式提示“未检测到可采集的真实 GPU”，不会伪造数据。

### 2. 启动后端

启动后端前，需要准备 `GPU_GOV_MASTER_KEY`，否则平台无法解密保存的凭据与运行时敏感数据。

```powershell
copy .\backend\.env.example .\backend\.env
cd .\backend
$env:GPU_GOV_MASTER_KEY = "replace-with-a-stable-random-secret"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`backend/.env.example` 中的关键配置包括：

- `GPU_GOV_MASTER_KEY`
- `AGENT_URL`
- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL`
- `NEO4J_URI`
- `NEO4J_USER`
- `NEO4J_PASSWORD`
- `LOCAL_NEO4J_HOME`
- `LOCAL_NEO4J_JAVA_HOME`

### 3. 启动前端

```powershell
cd .\frontend
npm ci --include=optional
npm run dev
```

默认情况下，前端开发代理会将请求转发到 `http://localhost:8000`。如果你手动修改了后端地址，可通过 `DEV_BACKEND_URL` 和 `DEV_BACKEND_WS_URL` 覆盖。

### 4. SSH Linux 模式要求

当你使用 SSH Linux 接入目标机时，目标环境至少需要满足：

- 目标主机可通过 SSH 登录
- 目标主机是 Linux
- 可执行 `nvidia-smi`
- 需要受控操作时具备 `sudo` 能力

平台会保存加密后的密码或私钥引用，供后续自动重连使用；是否可见这些保存记录取决于当前登录用户角色。

## Electron 与桌面开发

Electron 开发入口：

```powershell
.\start-electron-dev.bat
```

Windows 安装包构建：

```powershell
.\build-windows.bat
```

## 当前实现中的关键运行能力

以下能力已经在当前代码库中有实际实现入口：

- 平台登录、会话、用户隔离 workspace、已保存主机
- 独立导入层与导入范围隔离
- goal runtime 会把自然语言请求路由到聊天或执行链路，并维护会话上下文
- 智能工作台支持会话历史、审批、事件回放与流式响应
- 图谱工作台支持知识入图、图谱浏览、图谱问答与策略生成
- 集群控制台支持队列、作业、allocation、节点排空和自动调和
- control plane 统一承载人工操作与 Agent capability 调用

README 只做入口级说明。更细的实现细节请直接查看 `backend/app/services/goal_runtime/`、`backend/app/services/cluster_control/`、`backend/app/services/control_plane/` 和对应前端工作台代码。

## 开发校验

仓库级最小验证可以使用以下命令：

### Python 语法与导入检查

```powershell
python -m compileall .\backend\app .\server-agent
```

### 仓库级结构与回归测试

```powershell
python -m unittest discover -s .\tests -p "test_*.py"
```

### 后端服务测试

```powershell
python -m pytest .\backend\tests
```

### 前端测试与构建

```powershell
cd .\frontend
npm test
npm run build
```

## 安全与运行时数据

以下内容只应保留在本地，不应提交到公开仓库：

- `runtime/`
- `backend/data/`
- 任意 `.env`
- 真实 API Key
- 真实 SSH 凭据
- 平台身份数据库
- 运行日志、测试缓存、构建产物

平台会在公开 API 层面对部分敏感信息做脱敏，但仓库层面的密钥、凭据和运行时文件仍必须依赖 `.gitignore` 与本地环境隔离来保护。

## CI

GitHub Actions 当前执行的最小验证链路与本仓库本地建议基本一致：

- Python 依赖安装
- `compileall`
- 根级 `unittest`
- 前端 `npm test`
- 前端 `npm run build`

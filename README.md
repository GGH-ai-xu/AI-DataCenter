# GPU集群治理平台

面向共享 GPU 环境的运维、预算与公平治理平台。

本项目聚焦于把 GPU 资源管理做成一个可观测、可治理、可复盘的软件系统，而不是单纯的监控大屏或聊天式 AI 外壳。

## 项目定位

- 面向实验室、工作站、小型服务器等多用户共享 GPU 场景。
- 围绕“实时监测、任务治理、功率预算、能耗优化、调度回放”形成闭环。
- 强调真实采集、真实治理、真实可落地，而不是纯虚拟大屏。

## 当前运行方式

- 当前默认演示源为本机 `RTX 4060 Laptop GPU`。
- 已清理旧的虚拟/历史示例数据库，能耗统计会基于当前真实采集逐步累积。
- `TaskManager` 和 `Scheduler` 页面的部分操作会直接作用于真实进程与真实功耗上限，请谨慎操作。
- 稳定访问入口为 `http://localhost:8000/`。

## 核心能力

- 总功率预算治理：按全局功率上限统一管控多任务竞争。
- 任务优先级机制：支持紧急、普通、可延迟任务分级与资源让路。
- 用户占用可视化：从“看 GPU”升级到“看人、看任务、看治理结果”。
- 能耗治理与回放：展示能耗趋势、预算状态、优化建议与调度历史。
- 前后端一体交付：后端直接托管前端构建产物，便于本地部署与演示。

## 系统架构

1. `server-agent/`
   负责本机 GPU、系统资源、进程状态采集，以及功耗限制、任务暂停/恢复/终止等执行能力。
2. `backend/`
   负责数据聚合、历史存储、告警检测、调度治理、能耗分析、REST API 与 WebSocket 推送。
3. `frontend/`
   负责总览、任务治理、调度、能耗治理、告警、AI 辅助等交互界面。

## 快速启动

### 1. 安装依赖

```powershell
pip install -r .\backend\requirements.txt
pip install -r .\server-agent\requirements.txt
cd .\frontend
npm install
cd ..
```

### 2. 配置后端环境

```powershell
copy .\backend\.env.example .\backend\.env
```

只填写你自己的密钥与接口地址，不要把真实 `.env` 提交到 Git。

### 3. 一键启动

```powershell
powershell -ExecutionPolicy Bypass -File .\start_platform.ps1
```

如果你刚修改了前端，建议先重新构建：

```powershell
powershell -ExecutionPolicy Bypass -File .\start_platform.ps1 -BuildFrontend
```

### 4. 访问地址

- 平台首页：`http://localhost:8000/`
- 后端健康检查：`http://localhost:8000/api/health`
- 调度状态：`http://localhost:8000/api/scheduler/status`
- API 文档：`http://localhost:8000/docs`

## 手动启动方式

### 启动 Agent

```powershell
cd .\server-agent
python .\main.py
```

### 启动后端

```powershell
cd .\backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 构建前端

```powershell
cd .\frontend
npm run build
```

## 设计原则

- 不把项目做成“纯 AI 问答系统”，而是做成“GPU 治理平台”。
- 重点放在资源治理、预算约束、用户公平性、节能量化和真实部署闭环。
- 保持“发现问题 -> 给出治理策略 -> 执行干预 -> 回放结果”的完整软件链路。

## 安全说明

- 仓库已忽略 `.env`、`.claude/`、日志等敏感或本地运行文件。
- 推送前仍应再次检查是否误提交密钥、账号、主机地址、日志输出或个人路径信息。

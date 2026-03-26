# GPU 共享治理平台

面向共享 GPU 环境的治理工作台，重点不是“把数据画出来”，而是把真实采集、真实治理、真实复盘做成一个可交付的软件系统。

## 项目定位

- 服务对象：实验室工作站、小型服务器、多用户共享 GPU 环境。
- 核心目标：让 GPU 管理从“监控看板”升级为“治理工作台”。
- 设计原则：只基于真实数据给结论，没有真实数据时宁可提示“数据不足”，不再回退到模拟值。

## 当前能力

- 实时采集 GPU、系统资源和 GPU 进程数据。
- 支持任务暂停、恢复、终止与优先级治理。
- 支持总功率预算治理和单卡功耗上限控制。
- 支持用户公平性分析、额度规则和建议让路任务。
- 支持能耗分析、调度历史、治理回放和报告导出。
- 支持演练模式，危险动作可以先预演再真实执行。
- 对外接口默认做用户名、命令行、路径脱敏，降低泄露个人信息和主机路径的风险。

## 架构

### `server-agent/`

部署在本机或目标主机上，负责：

- GPU 实时状态采集
- 系统资源采集
- GPU 进程扫描
- 功耗限制、任务暂停/恢复/终止等真实执行能力

### `backend/`

负责：

- 聚合 Agent 数据
- 存储历史数据
- 告警检测与调度引擎
- 公平治理与能耗分析
- REST API 与 WebSocket
- 隐私脱敏与治理回放

### `frontend/`

负责：

- 治理工作台首页
- 任务处置台
- 预算治理台
- 观察台 / 回放台 / 风险台
- AI 辅助解释与报告展示

## 目录约定

```text
backend/        FastAPI 后端
server-agent/   本机执行与采集代理
frontend/       Vue 3 前端
tests/          基础单元测试
.github/        CI 工作流
```

## 本地运行

### 1. 安装依赖

```powershell
pip install -r .\backend\requirements.txt
pip install -r .\server-agent\requirements.txt
cd .\frontend
npm install
cd ..
```

### 2. 配置环境变量

```powershell
copy .\backend\.env.example .\backend\.env
```

只填写你自己的密钥与接口地址，不要提交真实 `.env`。

### 3. 启动 Agent

```powershell
cd .\server-agent
python .\main.py
```

### 4. 启动后端

```powershell
cd .\backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 5. 构建前端

```powershell
cd .\frontend
npm run build
```

构建完成后，后端会自动托管 `frontend/dist/`。

## 访问入口

- 平台首页：`http://localhost:8000/`
- 健康检查：`http://localhost:8000/api/health`
- 调度状态：`http://localhost:8000/api/scheduler/status`
- API 文档：`http://localhost:8000/docs`

## 安全与隐私

- 仓库已忽略 `.env`、日志、运行时目录和数据库文件。
- 前端与公开 API 默认返回脱敏后的用户名、命令和路径。
- 任务控制、单卡限功率、手动调度支持演练模式。
- 真实执行前需要明确风险确认，减少误操作。

## 开发校验

### 后端语法检查

```powershell
python -m compileall .\backend\app .\server-agent
```

### 单元测试

```powershell
python -m unittest discover -s .\tests -p "test_*.py"
```

### 前端构建

```powershell
cd .\frontend
npm run build
```

## CI

仓库内置 GitHub Actions 工作流，会自动执行：

- Python 依赖安装
- `compileall` 语法检查
- 基础单元测试
- 前端构建

## 当前约束

- 治理动作依赖本机真实权限；某些操作在权限不足时会被系统拒绝。
- 治理回放依赖历史数据累积，刚启动时样本会偏少。
- LLM 功能需要自行配置可用的兼容接口与密钥。

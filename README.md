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

## 核心算法

平台内置多个治理与分析算法，详细的数学公式、参数选择依据与对比实验见 [`docs/algorithm-report.md`](docs/algorithm-report.md)。

| 算法 | 用途 |
|------|------|
| EWA 指数加权平均 | 功耗与利用率短期趋势预测 |
| 线性回归 | 中期功耗趋势拟合 |
| 二次多项式拟合 | 非线性趋势捕捉（含防发散保护） |
| 自动择优 | 逐小时 RMSE 竞选，自动选择最佳预测方法 |
| 公平性评分（6 因子） | 量化多用户资源占用均衡度 |
| 让路评分（5 因子） | 综合优先级、份额、内存、运行时和违规排序候选任务 |
| 效率评分 | 利用率-功率比 + 温度惩罚 |
| 碳排放核算 | 基于国网 2023 碳因子 0.5703 kgCO₂/kWh |

## 前端组件架构

前端采用 Vue 3 Composition API，视图层通过 composable 共享跨页面逻辑，业务组件按领域拆分：

```text
frontend/src/
  composables/           跨视图共享逻辑
    useExecutionMode.js    执行模式（演练/真实）
    useActionFeedback.js   操作反馈通知
    useDashboardData.js    首页数据聚合
    useTaskManagerData.js  任务治理数据
    ...
  components/
    dashboard/           首页组件
    tasks/               任务治理组件
    workspace/           布局壳组件
    alerts/              告警组件
  views/                 页面视图（6 个主视图）
```

## 目录约定

```text
backend/        FastAPI 后端
server-agent/   本机执行与采集代理
frontend/       Vue 3 前端
tests/          单元测试与算法基准（213 项）
docs/           算法报告与测试报告
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

## 安装后怎么用

### 一键演示启动

本机演示模式：

```powershell
.\launch-demo.bat
```

只启动后端，准备接远程服务器：

```powershell
.\launch-demo.bat -SkipAgent
```

### 接入方式切换

平台首页提供“接入中心”，支持两种模式：

- 本机模式：连接当前电脑上的 `server-agent`
- 远程服务器模式：连接你指定服务器上的 `server-agent`

切换方式：

1. 打开首页“接入中心”
2. 选择“本机模式”或“远程服务器模式”
3. 远程模式下填写 `http://服务器IP:8001`
4. 先点“测试连接”，再点“保存并切换”

这样安装好之后，同一套前端和后端可以接当前电脑，也可以接某台服务器，不需要再手改 `.env`。

## Windows 桌面版打包

如果要生成真正的 Windows 桌面安装器：

```powershell
.\build-windows.bat
```

打包完成后会生成：

- `dist/electron/GPUGovernanceWorkbench-Setup-1.1.0.exe`
- `dist/electron/win-unpacked/`

说明：

- `GPUGovernanceWorkbench-Setup-1.1.0.exe` 是正式安装器
- `win-unpacked/` 是免安装测试目录，可直接运行

桌面版形态：

- 双击后打开独立桌面窗口，不再弹浏览器
- 桌面壳内部会自动拉起后端和本机 Agent
- 首页仍可切换“本机模式 / 远程服务器模式”

如果你只想重新生成 Python 运行时目录而不打桌面安装器：

```powershell
.\build-runtime-windows.bat
```

## 访问入口

- 平台首页：`http://localhost:8000/`
- 健康检查：`http://localhost:8000/api/health`
- 接入配置：`http://localhost:8000/api/system/connection`
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
python -m pytest tests/ -v
```

213 项测试覆盖：

- **核心算法基准**（35 项）：EWA/线性/多项式预测精度、公平性评分边界、让路评分单调性、碳排放计算
- **调度引擎**（22 项）：温度规则、功率预算、碳预算、tick 编排、参数校验
- **公平治理**（33 项）：6 因子评分、分布差距、规则违规、让路排序、可治理判定
- **能耗预测**（30 项）：三种预测算法行为、效率评分、规则建议、时段分类
- **数据统计**（9 项）：聚合查询、采集时长、吞吐率计算
- **工程质量**（84 项）：前端结构、启动脚本、性能热路径、隐私脱敏

详细测试报告见 [`docs/test-report.md`](docs/test-report.md)。

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

# GPU 共享治理平台

面向共享 GPU 环境的治理工作台。项目重点不是“展示监控图表”，而是把真实采集、真实治理、真实复盘和受控执行做成一套可交付的软件系统。

## 当前模型

- 平台先做用户登录，再进入独立导入准备页。
- 导入准备页支持三种来源：本机 Agent、远程 Agent、SSH Linux。
- 扫描通过后，用户勾选“本次纳入治理”的 GPU，再进入控制台。
- 控制台只显示和治理本次导入选中的卡，不再承担连接切换逻辑。
- 已保存主机会按用户隔离保存；管理员可查看全部主机记录，普通用户只能查看自己的。

## 目录结构

```text
backend/        FastAPI 后端、平台身份、导入层、治理 API
server-agent/   本机/目标机上的采集与控制 agent
frontend/       Vue 3 + Vite 控制台与导入层 UI
desktop-shell/  Electron 桌面壳
scripts/        Windows 开发、依赖安装、桌面打包脚本
tests/          仓库级回归测试
```

## 快速开始

推荐在 Windows 开发机上使用仓库自带脚本：

```powershell
.\install-deps.bat
.\start-dev.bat
```

`start-dev.bat` 会自动：

- 启动本机 agent、backend、frontend
- 清理残留的仓库托管进程
- 为平台生成或复用本地运行主密钥 `runtime/.gpu-gov-master-key`

启动完成后，打开启动器打印的 Frontend URL。

## 首次登录与导入流程

1. 首次启动后，后端会自动创建默认管理员 `admin`。
2. 默认密码为 `admin123456`。
3. 默认管理员可直接登录进入导入层，后续可按需修改密码。
4. 登录后进入导入准备页，选择本机 Agent、远程 Agent 或 SSH Linux。
5. 扫描目标机器，确认 CPU / GPU 信息并勾选本次导入 GPU。
6. 导入完成后进入控制台，后续监控和治理只作用于本次导入范围。

## 接入模式

### 本机 Agent

适用于当前机器本地部署的 `server-agent`。

### 远程 Agent

适用于目标主机上已经运行 `server-agent`，平台通过 HTTP 接入。

### SSH Linux

适用于目标主机不运行 agent，而是由平台通过 SSH 直接读取 Linux 与 NVIDIA 数据。

要求：

- 目标主机可通过 SSH 登录
- 目标主机是 Linux
- 可执行 `nvidia-smi`
- 需要时具备 `sudo` 能力

SSH Linux 模式下，平台会保存加密后的密码或私钥引用，供后续自动重连使用。

## 手动启动

如果不使用 `start-dev.bat`，可以分别启动各服务。

启动本机 agent：

```powershell
cd .\server-agent
python .\main.py
```

启动后端前，请先设置 `GPU_GOV_MASTER_KEY`，否则平台无法解密保存的 SSH 凭据：

```powershell
copy .\backend\.env.example .\backend\.env
cd .\backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

启动前端：

```powershell
cd .\frontend
npm ci --include=optional
npm run dev
```

## 桌面壳与打包

Electron 开发入口：

```powershell
.\start-electron-dev.bat
```

Windows 安装包构建：

```powershell
.\build-windows.bat
```

## 安全说明

以下内容只应保留在本地，不应提交到公开仓库：

- `runtime/` 下的主密钥、导入上下文、已保存主机凭据、平台身份数据库
- `backend/data/` 下的历史数据库
- 任意 `.env`、真实 API Key、真实 SSH 凭据
- 本地构建产物、日志、测试缓存

平台默认会对公开 API 返回的用户名、命令行和路径做脱敏处理，但仓库层面的密钥和运行时文件仍必须由 `.gitignore` 保护。

## 环境变量

公开示例位于 `backend/.env.example`。

其中最关键的是：

- `GPU_GOV_MASTER_KEY`：平台身份与已保存 SSH 凭据的解密主密钥
- `AGENT_URL`：本机默认 agent 地址
- `LLM_*`：可选的 OpenAI 兼容接口配置

## 开发校验

Python 语法检查：

```powershell
python -m compileall .\backend\app .\server-agent
```

仓库级单元测试：

```powershell
python -m unittest discover -s .\tests -p "test_*.py"
```

前端测试：

```powershell
cd .\frontend
npm test
```

前端生产构建：

```powershell
cd .\frontend
npm run build
```

## CI

GitHub Actions 会执行与当前仓库一致的最小验证链路：

- Python 依赖安装
- `compileall` 检查
- 根级 `unittest`
- 前端 `npm test`
- 前端 `npm run build`

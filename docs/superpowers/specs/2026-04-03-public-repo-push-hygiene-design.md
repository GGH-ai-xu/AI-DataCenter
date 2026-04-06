# Public Repo Push Hygiene Design

## Goal

在不改变现有产品行为的前提下，把仓库整理到适合对外共享的状态：本地运行态与敏感材料默认不入库，外部协作者能看懂当前架构与启动流程，基础协作配置与 CI 反映当前真实实现。

## Scope

本次只整理以下内容：

- 根目录协作配置：`.gitignore`、`.editorconfig`、`.gitattributes`
- 面向协作者的入口文档：`README.md`
- 后端公开环境示例：`backend/.env.example`
- GitHub Actions 基线校验：`.github/workflows/ci.yml`

不做的事：

- 不调整业务功能和页面行为
- 不清理历史设计/计划文档
- 不扩展到发布模板、License、Issue/PR 模板体系

## Design

### 1. Repository Hygiene

明确排除 `runtime/`、主密钥、凭据存储、平台身份数据库、缓存、coverage、工作树目录和构建产物；保留当前确实需要版本化的构建资源例外项。

### 2. Collaboration Baseline

新增 `.editorconfig` 和 `.gitattributes`，统一跨平台提交的基础行为：大部分源码文本使用 LF，Windows 启动脚本与 PowerShell 脚本保持 CRLF 优先；Python 4 空格，前端/YAML/JSON/Markdown 2 空格。

### 3. Public-Facing Docs

把 README 改为当前真实用户路径：

1. 启动依赖与服务
2. 首次登录默认管理员并立即改密
3. 在导入准备页选择本机 Agent、远程 Agent 或 SSH Linux
4. 扫描硬件并勾选本次导入 GPU
5. 进入只治理本次导入 GPU 的控制台

同时明确 SSH Linux 模式不要求目标主机运行 agent，但要求可用 SSH、`nvidia-smi` 与 Linux 系统接口。

### 4. CI Alignment

CI 保持“当前稳定可执行”的最小集合：

- Python `compileall`
- 根级 `unittest`
- 前端 `npm test`
- 前端 `npm run build`

不额外引入未验证的新检查器。

## Risks

- README 如果继续保留旧的“首页接入中心切换模式”说法，会让外部协作者误解当前入口。
- 若 `.gitattributes` 处理不当，会引入整仓行尾抖动，因此只设置明确的文本规则，不批量重写无关文件。

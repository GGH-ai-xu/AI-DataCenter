# SSH Linux Provider 接入设计

## 背景

当前项目的运行时接入模型是 `Agent-first`：后端通过 `AgentClient` 访问目标主机上的 HTTP Agent，由 Agent 提供 GPU、系统、进程采集以及功耗和任务治理能力。导入层已经前置到独立 `/import` 页面，但其接入来源仍只支持本机 Agent 或远程 Agent。

用户希望新增一条不依赖目标机部署 Agent 的接入路径：通过 SSH 直接连接 Linux 目标机，在导入层完成探测与选卡后进入控制台，并在控制台中持续监控和治理本次导入的 GPU。

## 目标

- 新增 `ssh_linux` 运行时来源，支持无 Agent 接入 Linux 目标机。
- 支持 SSH 用户名密码和私钥两种认证方式。
- 支持保存凭据到后端，用于控制台运行期自动重连。
- 支持可选 `sudo` 执行，用于功耗设置和进程治理等高权限动作。
- 控制台继续只显示和治理“本次导入选中的卡”。
- 目标机断线时优先自动重连，仅在连续失败超阈值后回退到 `/import`。

## 非目标

- 本次不支持 Windows 目标机。
- 本次不上传脚本、不安装常驻进程、不在目标机部署轻量 Agent。
- 本次不支持多目标并行导入，也不维护多套同时活跃的导入上下文。
- 本次不做静默降级；能力不足或探测失败必须显式返回错误。

## 方案对比

### 方案 A：双 Provider 架构

定义统一运行时接口，将现有 HTTP Agent 适配为 `HttpAgentProvider`，新增 `SshLinuxProvider`。控制台、采集循环、调度器、AI 控制和系统自检只依赖抽象接口，不关心底层协议。

优点：

- 清晰隔离 HTTP Agent 和 SSH 两套实现。
- 可复用现有导入上下文、范围过滤和控制台展示逻辑。
- 后续继续扩展 WinRM、K8s 或其他 provider 时有明确边界。

缺点：

- 需要改造当前直接依赖 `AgentClient` 的调用点。

### 方案 B：在 `AgentClient` 内混合支持 HTTP 和 SSH

保留单个客户端类，根据模式决定是发 HTTP 还是执行 SSH 命令。

优点：

- 表面改动面较小。

缺点：

- 协议、连接、凭据、sudo、重连和错误模型会混在同一个类中。
- 长期维护成本高，后续继续扩展时边界会失控。

### 方案 C：本地桥接“微 Agent”

后端继续只连 HTTP 接口，但在治理后端侧新增一层 SSH 桥接服务，把 SSH 命令包装成 HTTP。

优点：

- 对现有 HTTP 调用点侵入最小。

缺点：

- 本质仍是 Agent 方案，只是换了部署位置。
- 复杂度被转移而非消除，不符合“无 Agent 接入”的目标。

## 推荐方案

采用方案 A，新增统一 `RuntimeProvider` 抽象和 `SshLinuxProvider` 实现。这样既能保持导入层与控制台的现有边界，也能把 SSH 特有的认证、sudo、命令解析和重连逻辑限制在 provider 层。

## 后端架构

### RuntimeProvider 抽象

新增统一运行时接口，最少覆盖以下能力：

- `health_check()`
- `get_all_gpus()`
- `get_system_info()`
- `get_processes()`
- `set_power_limit()`
- `pause_task()`
- `resume_task()`
- `terminate_task()`
- `close()`

现有 HTTP Agent 实现迁移为 `HttpAgentProvider`，逻辑主体复用现有 `AgentClient`。

### RuntimeProviderManager

新增运行时管理器，负责：

- 保存当前控制台绑定的 provider 实例。
- 基于导入提交结果原子切换当前 provider。
- 维护最近健康状态、离线状态和重连状态。
- 在 provider 断线时按固定间隔重连。
- 在连续重连失败达到阈值后，将导入上下文标记失效。

采集循环、调度器、AI 控制、系统自检和治理服务不再直接持有 `AgentClient`，而是依赖当前 provider。

### 配置与凭据分层

现有 `ConnectionSettingsService` 需要泛化为目标配置服务，配置字段按“非敏感配置”和“敏感凭据”分层：

非敏感配置：

- `provider_type`
- `label`
- `agent_url`
- `host`
- `port`
- `username`
- `auth_type`
- `sudo_enabled`
- `credential_id`

敏感凭据：

- SSH 密码
- 私钥内容
- 私钥口令
- sudo 密码

敏感字段不与普通运行配置混写，改由单独的 `CredentialStore` 持久化并在 API 响应中统一脱敏。

## 导入层与 API 设计

### provider 类型

导入层从现在的 `local / remote` 升级为明确的 provider 类型：

- `http_local`
- `http_remote`
- `ssh_linux`

控制台仍然只读展示当前来源，不再内嵌切换逻辑。

### SSH 导入表单

`/import` 在 `ssh_linux` 模式下新增字段：

- 主机地址
- 端口
- 用户名
- 认证方式：密码或私钥
- 密码
- 私钥
- 私钥口令
- 是否启用 sudo
- sudo 密码
- 目标标签

### 扫描接口

`POST /api/system/import-context/scan` 接收统一 provider 配置，执行真实探测但不切换当前控制台 provider，返回：

- provider 类型和规范化目标配置
- 认证是否成功
- sudo 是否可用
- `nvidia-smi` 是否可用
- Agent 或 SSH 目标健康状态
- CPU / 内存 / 负载摘要
- 全部 GPU 当前状态
- 需要用户处理的错误明细

### 提交导入接口

`POST /api/system/import-context` 在提交时重新做一次验证，确认：

- 认证仍然有效
- 选中的 GPU 索引存在
- provider 必需能力可用

通过后：

1. 保存目标配置。
2. 保存或更新凭据。
3. 创建并切换当前 provider。
4. 保存导入上下文。
5. 返回新的 `import_context` 和运行时状态。

## SshLinuxProvider 行为

### 采集来源

仅使用目标机现有命令和 `/proc`：

- GPU：`nvidia-smi --query-gpu=... --format=csv,noheader,nounits`
- GPU 进程：`nvidia-smi --query-compute-apps=pid,gpu_uuid,used_memory --format=csv,noheader,nounits`
- 进程详情：`ps -o pid=,user=,comm=,args=,etimes=` 或 `/proc/<pid>`
- CPU 与内存：`nproc`、`free -b`、`/proc/stat`、`/proc/meminfo`
- 负载：`/proc/loadavg`

采集结果需要转换为现有前端可消费的结构，避免前端再区分 provider。

### 治理动作

治理命令同样通过现有系统命令执行：

- 功耗限制：`nvidia-smi -i <index> -pl <watts>`
- 暂停进程：`kill -STOP <pid>`
- 恢复进程：`kill -CONT <pid>`
- 终止进程：`kill -TERM <pid>`，必要时补 `kill -KILL <pid>`

### sudo 执行

新增统一命令执行器，例如 `SshCommandExecutor`，集中处理：

- 普通命令执行
- `sudo -S` 包装
- sudo 密码输入
- 超时和 stderr 捕获

业务层不直接拼接 sudo 逻辑，避免控制代码散落。

### 健康检查与重连

SSH provider 维护可重建连接状态。断线时：

1. 进入 `reconnecting` 状态。
2. 后台按固定间隔尝试重连。
3. 重连成功后恢复采集与治理。
4. 连续失败达到阈值后，把当前导入上下文标记失效并触发前端退回 `/import`。

重连失败前，不立即清空当前导入上下文。

## 导入上下文与控制台范围

现有 `ImportContextService` 继续负责：

- 持久化当前导入上下文
- 过滤 GPU 列表
- 过滤进程列表
- 校验治理目标是否越界

导入上下文模型需要补充 provider 维度，例如：

- `provider_type`
- `source_label`
- `target_summary`

控制台现有页面继续只消费过滤后的 GPU 和进程数据，不重新引入协议判断。

## 错误模型

坚持显式失败：

- 认证失败时返回明确错误，不伪造“空设备”结果。
- `nvidia-smi` 缺失时明确说明目标机不满足 GPU 采集前提。
- SSH 导入必须同时满足监控和治理前提；若当前 SSH 用户无足够权限且 sudo 也不可用，则扫描明确报错并拒绝提交导入。
- 治理动作失败时返回命令类别和 stderr 摘要。
- 断线时先显示重连状态，超阈值后再标记导入失效。

## 测试策略

### 单元测试

- provider 配置解析
- 凭据脱敏
- SSH 命令输出解析
- sudo 执行路径
- 导入上下文状态迁移
- 重连状态机

### 后端服务测试

- `scan` / `commit` 新 schema
- provider 切换
- 导入范围过滤
- SSH 治理越界拒绝
- 断线自动重连和失效回退

### 前端测试

- `/import` 在 `ssh_linux` 模式下展示 SSH 表单
- 密码/私钥模式切换
- 扫描结果展示
- 导入成功后进入控制台
- SSH 运行时离线与重连状态展示

## 实施拆分

### 第一步：引入 provider 抽象

- 新增 `RuntimeProvider` 和 `RuntimeProviderManager`
- 将现有 HTTP Agent 迁移为 `HttpAgentProvider`
- 保持现有行为不变并通过回归测试

### 第二步：扩展导入层与配置模型

- 扩展 provider 类型和 SSH 表单
- 新增凭据存储
- 打通 SSH 扫描链路

### 第三步：接入 SSH 运行时能力

- 实现 `SshLinuxProvider`
- 接入采集循环、治理动作、调度和 AI 控制
- 保证控制台数据结构对前端保持兼容

### 第四步：补齐重连与回退

- 实现自动重连状态机
- 补齐导入失效与前端跳转逻辑
- 完成结构测试、后端测试和前端测试回归

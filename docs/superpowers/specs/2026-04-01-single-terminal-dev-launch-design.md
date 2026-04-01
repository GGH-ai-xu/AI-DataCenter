# Single-Terminal Dev Launch Design

## Goal

将 `start-dev.ps1` 和 `start-electron-dev.ps1` 改为单终端开发入口。Agent、Backend、Frontend 保持并行运行，但日志统一输出到当前终端，并按服务增加稳定前缀，避免开发时出现多个 PowerShell 窗口。

## Current Problem

- `start-dev.ps1` 当前为 Agent、Backend、Frontend 各自打开独立 PowerShell 窗口。
- `start-electron-dev.ps1` 当前也为三个服务分别打开终端，虽然 Electron 主窗口已不再走 PowerShell 宿主，但整体仍会产生过多终端。
- 多窗口模式会分散日志上下文，定位跨服务问题时需要在多个终端之间切换。

## Chosen Approach

采用“主控制器脚本 + 后台子进程 + 单终端日志聚合”方案。

- `start-dev.ps1` 和 `start-electron-dev.ps1` 自身成为长驻控制器。
- Agent、Backend、Frontend 不再通过 `Start-Process powershell -NoExit` 启动，而是由主脚本直接创建子进程。
- 主脚本接管各子进程的 `stdout` 和 `stderr`，逐行打印到当前终端。
- 每行日志使用统一格式：`HH:mm:ss [Service] message`。
- Electron 入口继续直接启动桌面壳窗口，但不额外创建日志终端。

## Process Model

### Shared behavior

- 保留现有动态端口分配逻辑和健康检查逻辑。
- 子进程启动顺序保持为 Agent -> Backend -> Frontend。
- 只有前一服务健康检查通过后，才启动下一服务。
- 每个子进程的环境变量仍由脚本显式注入，不改用户全局环境。

### Log handling

- 为每个服务单独建立输出读取器。
- `stdout` 与 `stderr` 都进入统一终端输出，且保留服务名标签。
- 不做静默降级，不吞掉错误行。
- 如果某个子进程退出，应在终端输出明确退出信息，包括服务名和退出码。

### Shutdown behavior

- 主脚本监听终端退出或中断。
- 当主脚本结束时，负责终止所有由其拉起的子进程，避免遗留 Agent、Backend、Frontend 进程。
- Electron 开发入口只管理它直接拉起的后台服务，不尝试接管用户已手动启动的其它实例。

## Script Changes

### `scripts/start-dev.ps1`

- 删除多窗口启动函数，替换为后台子进程启动与日志泵送函数。
- 保留浏览器自动打开逻辑。

### `scripts/start-electron-dev.ps1`

- 删除 Agent、Backend、Frontend 的多窗口启动逻辑。
- 保留 Electron 直接启动逻辑。
- Electron 主窗口不进入统一日志聚合；它仍作为独立 GUI 进程启动。

## Testing Strategy

- 更新 `tests/test_start_dev_scripts.py`，要求两个脚本都不再包含旧的多窗口启动模式。
- 增加针对单终端日志聚合函数和进程清理函数的结构性断言。
- 使用 Windows 环境运行 `py -3 -m unittest tests.test_start_dev_scripts -v`。
- 使用 PowerShell 解析两个脚本，确保无语法错误。

## Non-Goals

- 不修改后端、Agent、前端应用本身的日志格式。
- 不引入日志文件轮转或持久化。
- 不改变 Electron 图标、AppUserModelID、端口策略和健康检查接口。

## Risks and Handling

- PowerShell 异步读取子进程输出比多窗口启动更复杂，因此实现时必须保持函数边界清晰。
- 如果日志泵送与健康检查耦合，脚本会变得难以维护，因此健康检查、进程启动、输出转发、进程清理必须拆分为独立函数。

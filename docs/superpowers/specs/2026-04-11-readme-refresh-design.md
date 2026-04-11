# README 更新设计

## 背景

当前 [README.md](/mnt/e/code/ai-datacenter/README.md) 仍主要覆盖早期的“导入 + 控制台 + 基础启动”阶段，尚未反映当前代码库已经落地的关键能力与结构，包括：

- 平台登录、用户隔离 workspace、导入层三种接入方式
- 治理台统一入口与 control plane
- AI 双工作台：智能工作台与图谱工作台
- goal runtime、审批、会话事件与流式问答
- 集群控制：queue、job、allocation、reconcile
- Windows 开发脚本、可选本地 Neo4j、Electron 桌面壳

这导致 README 不能同时胜任“新开发者快速上手”和“现有代码库能力总览”两类职责。

## 目标

将 README 重构为一份兼顾上手与总览的入口文档，满足以下目标：

1. 新读者在 3 分钟内理解项目定位、核心能力和主要工作流。
2. 开发者能根据 README 找到启动方式、关键目录和核心依赖。
3. 文档描述必须与当前代码库实际实现一致，不虚构未落地能力。
4. 不把 README 膨胀成完整架构手册，复杂细节仍留给代码与 `docs/`。

## 非目标

- 不新增功能，不借 README 更新顺带改业务实现。
- 不在这次任务里重建完整文档体系。
- 不把 README 改成纯营销页或纯 API 参考手册。

## 事实来源

本次 README 更新只以当前代码库为依据，主要来自：

- [README.md](/mnt/e/code/ai-datacenter/README.md)
- [frontend/src/main.js](/mnt/e/code/ai-datacenter/frontend/src/main.js)
- [frontend/src/views/AIWorkspaceLayout.vue](/mnt/e/code/ai-datacenter/frontend/src/views/AIWorkspaceLayout.vue)
- [frontend/src/views/AIAssistant.vue](/mnt/e/code/ai-datacenter/frontend/src/views/AIAssistant.vue)
- [frontend/src/views/AIGraphWorkspace.vue](/mnt/e/code/ai-datacenter/frontend/src/views/AIGraphWorkspace.vue)
- [frontend/src/views/ClusterJobs.vue](/mnt/e/code/ai-datacenter/frontend/src/views/ClusterJobs.vue)
- [backend/app/main.py](/mnt/e/code/ai-datacenter/backend/app/main.py)
- [server-agent/main.py](/mnt/e/code/ai-datacenter/server-agent/main.py)
- [backend/.env.example](/mnt/e/code/ai-datacenter/backend/.env.example)
- [scripts/start-dev.ps1](/mnt/e/code/ai-datacenter/scripts/start-dev.ps1)
- [push日志.txt](/mnt/e/code/ai-datacenter/push日志.txt)

## 推荐方案

采用“分层总览版”：

1. 先说明项目定位与核心能力，让读者先知道系统是什么。
2. 再给出真实工作流与目录结构，让读者知道系统怎么用、代码在哪。
3. 最后补充启动方式、依赖、验证、安全边界，让开发者能直接开始工作。

该方案比“最小修补版”更清晰，也比“README + 深文档跳转版”更适合本次只更新 README 的任务范围。

## README 目标结构

README 将重构为以下章节：

### 1. 项目定位

明确本项目不是单纯 GPU 监控面板，而是一个围绕“登录、导入、治理、AI、图谱、集群控制”组织的智算治理平台。

### 2. 核心能力总览

基于当前路由与页面结构，概括六个主入口和 AI 双工作台：

- 总览
- 治理
- 能耗
- 观察
- 告警
- 智能
- 智能工作台 / 图谱工作台

并说明这些入口对应的功能边界，而不是泛泛罗列。

### 3. 典型工作流

用面向使用者的方式描述主流程：

1. 登录平台
2. 进入独立导入层
3. 选择接入模式并扫描目标
4. 勾选本次纳入治理的 GPU
5. 进入控制台进行治理、复盘、AI 问答或图谱分析

### 4. 系统架构与目录

保留目录结构，但补足其职责：

- `backend/`
- `server-agent/`
- `frontend/`
- `desktop-shell/`
- `scripts/`
- `tests/`
- `runtime/` 的运行时属性与不可提交性质

### 5. 快速启动

优先说明 Windows 下的推荐入口：

- `install-deps.bat`
- `start-dev.bat`

并明确 `start-dev.bat` 实际会拉起 Agent、Backend、Frontend，且会尝试准备本地 Neo4j。

### 6. 手动启动与关键依赖

说明以下内容：

- Agent、Backend、Frontend 的独立启动方式
- `GPU_GOV_MASTER_KEY`
- 可选 LLM 配置
- 可选 Neo4j 配置
- SSH Linux 模式对目标机的要求

### 7. 当前实现中的关键运行能力

用简洁方式补充当前已落地能力：

- goal runtime / 审批 / 会话事件
- 图谱入图、问答、策略生成
- 集群作业、队列、allocation、自动调和
- 控制面统一承载人工操作与 Agent 操作

这一节只写“已落地能力的摘要”，不展开实现细节。

### 8. 开发验证

列出当前仓库实际使用的最小验证命令：

- Python `compileall`
- 根级 `unittest`
- 前端 `npm test`
- 前端 `npm run build`

### 9. 安全与运行时数据

明确哪些目录与文件不能提交，以及为什么：

- `runtime/`
- `backend/data/`
- `.env`
- 凭据、密钥、构建产物、日志

## 文案策略

- 用户可见说明保持中文，命令与路径保持英文/原样。
- 用“事实性说明”替代宣传性表述。
- 避免描述“未来想做什么”，只描述当前仓库已经具备什么。
- 对复杂能力保持克制，用一两句话说明定位，不在 README 中展开内部实现。

## 风险与控制

### 风险 1：README 变长后失去可读性

控制方式：采用“先总览、后细节”的顺序，每节只保留进入项目所需的最小信息。

### 风险 2：把未完全稳定的能力写成既成事实

控制方式：所有表述以当前代码入口、服务模块和已有路由为准，不凭 `push日志.txt` 单独扩写。

### 风险 3：与现有启动脚本说明不一致

控制方式：以 [scripts/start-dev.ps1](/mnt/e/code/ai-datacenter/scripts/start-dev.ps1) 和 [backend/.env.example](/mnt/e/code/ai-datacenter/backend/.env.example) 为最终依据。

## 验证计划

README 更新完成后，做最小验证：

1. 用 Windows Python 执行 `compileall`，确认文档提到的代码结构与仓库至少能被解释器扫描。
2. 用 Windows Node 执行前端 `npm run build`，确认文档提到的开发入口仍与当前项目结构兼容。

## 完成标准

满足以下条件即视为完成：

- README 已覆盖当前系统的主要入口、工作流、目录和启动方式
- 内容与当前代码一致
- 不改动无关代码
- 完成最小验证并记录结果

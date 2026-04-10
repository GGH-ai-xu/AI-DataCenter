# AI Dual Workspace Design

## 背景

当前合并分支已经同时吸收了两类 AI/Agent 能力：

- 本地主线的 `goal_runtime + AgentWorkbench` 智能工作台
- 远端引入的 `graph + Neo4j + 图谱问答/导入/策略生成` 能力

但这两类能力没有形成两个都可访问、可运行的前端入口：

- `frontend/src/views/AIAssistant.vue` 只保留了当前本地主线的工作台入口
- 远端带来的 `frontend/src/components/ai/*` 和 `frontend/src/composables/useGraphWorkspace.js` 已存在，但没有页面挂载
- 后端 graph API 已注册，前端 graph UI 仍是孤立代码

因此问题不是“是否保留 graph 能力”，而是“如何让两套能力都能跑，同时不破坏当前智能页的信息架构原则”。

## 目标

本轮目标是让两套 AI 能力都具备明确入口并可独立运行：

- 保留当前 `AI 助手工作台` 作为默认智能页，不回退到旧多标签控制台
- 在智能域内新增一个并列子页，承接远端 graph 版本能力
- 不把图谱导入、图谱问答、策略生成塞回当前 `AIAssistant.vue`
- 保持控制面和图谱面的职责边界清晰

## 非目标

本轮不做以下事情：

- 不把 graph UI 混入当前聊天工作台主界面
- 不新建第三套 AI 架构
- 不重写 graph 后端协议
- 不调整主侧栏的一级导航数量

## 方案选择

### 方案 A：在“智能”下拆成两个子页

- `智能工作台`：保留当前 `AIAssistant.vue`
- `图谱智能`：新增独立 view，挂载 graph import / catalog / qa / strategy

优点：

- 最符合当前本地主线“页面主轴清晰”的原则
- 当前工作台不用回退
- graph 版本有独立入口，后续可独立演进
- 两套能力都能跑，职责边界明确

缺点：

- 智能模块恢复为二级分页结构
- 需要补一页新的 view 和路由

### 方案 B：把 graph 做成当前工作台的弹出面板

优点：

- 路由改动最少

缺点：

- 会再次污染当前工作台主界面
- 图谱操作本身信息密度高，不适合塞进弹层
- 与现有“减少冗余、突出主体”的设计方向冲突

### 方案 C：新增一级导航

优点：

- 物理隔离最强

缺点：

- 破坏目前已经收紧到 6 个一级入口的导航原则
- 用户会把 graph 误解成独立域，而不是智能域的一种能力面

## 选择

采用方案 A。

理由：

- 它同时满足“两个版本都可跑”和“遵守当前本地主线 UI 原则”
- 当前 `AIAssistant.vue` 可以原样保留，风险最低
- graph 入口被恢复为独立可访问页面，而不是孤立代码

## 信息架构

智能模块改为二级工作区：

- `workbench`
  - 名称：智能工作台
  - 内容：当前 `AgentWorkbench`、模型配置、权限切换、runtime 会话
- `graph`
  - 名称：图谱智能
  - 内容：graph import、graph catalog、graph qa、graph strategy

一级导航仍然保持：

- `/ai`

二级路由收敛为：

- `/ai/workbench`
- `/ai/graph`

并保持：

- `/ai` 默认重定向到 `/ai/workbench`

## 页面边界

### 智能工作台

保留当前页面逻辑：

- 使用 `AgentWorkbench`
- 使用 `useAiAssistantWorkbench`
- 使用 `useAiAssistantLlm`
- 使用 `/api/ai/workbench/dispatch`
- 使用 `/api/agent-runtime/*`

这个页面不再承载 graph 相关入口与状态。

### 图谱智能

新页面职责：

- 作为远端 graph 版本的唯一前端承接页
- 使用现有 `useGraphWorkspace.js`
- 组织已有的 graph 组件：
  - `GraphImportPanel.vue`
  - `GraphCypherPreview.vue`
  - `GraphExecuteResult.vue`
  - `GraphCatalogViewer.vue`
  - `GraphQAPanel.vue`
  - `GraphStrategyGenerator.vue`

该页面内部允许继续使用二级 tabs，因为 graph 本身是一个高信息密度工作区，和当前 AI 聊天工作台不同。

## 路由设计

现有 `frontend/src/main.js` 中 `/ai` 目前是单页面路由：

- `/ai` -> `AIAssistant.vue`

调整后结构：

- `/ai`
  - component: 一个新的智能域壳层，例如 `AIWorkspaceLayout.vue`
  - children:
    - `/ai/workbench` -> `AIAssistant.vue`
    - `/ai/graph` -> `AIGraphWorkspace.vue`
    - `/ai` -> redirect `/ai/workbench`

这样可以：

- 不改变一级导航路径
- 在智能域内部引入二级 tabs
- 避免把 graph 内容混入工作台页面本身

## 组件分解

新增：

- `frontend/src/views/AIWorkspaceLayout.vue`
  - 智能域二级壳层
  - 负责 `WorkspaceTabs`
  - 不承载具体业务状态

- `frontend/src/views/AIGraphWorkspace.vue`
  - 图谱智能页
  - 负责组合 graph workspace 的四块能力

保留：

- `frontend/src/views/AIAssistant.vue`
  - 继续作为工作台页

复用：

- `frontend/src/composables/useGraphWorkspace.js`
- `frontend/src/components/ai/*`

## 数据流

### 智能工作台链路

用户输入 -> `useAiAssistantWorkbench` -> `/api/ai/workbench/dispatch` -> chat 或 runtime -> UI 渲染

### 图谱智能链路

用户输入论文/知识内容 -> `useGraphWorkspace` -> `/api/graph/draft` / `/api/graph/execute` / `/api/graph/qa` / `/api/graph/view` -> 图谱页渲染

两条链路共享：

- LLM 配置
- 平台登录鉴权
- 同一个智能一级导航域

但不共享页面状态。

## 兼容性原则

- `AIAssistant.vue` 不回退成旧版多标签页
- graph UI 不再作为孤立代码存在，必须有真实页面入口
- 不保留临时兼容层去同时支持“旧 AI 单页多标签”和“新双页结构”
- 若现有测试断言 `AIAssistant.vue` 不使用 `WorkspaceTabs`，则应把 tabs 上移到新的 `AIWorkspaceLayout.vue`，而不是改回旧页面

## 测试要求

需要覆盖：

- 路由：
  - `/ai` 重定向到 `/ai/workbench`
  - `/ai/graph` 可进入 graph 页面

- 结构：
  - `AIAssistant.vue` 仍使用 `AgentWorkbench`
  - `AIGraphWorkspace.vue` 真实挂载 graph 组件
  - `AIWorkspaceLayout.vue` 使用 `WorkspaceTabs`

- API：
  - graph 页面真实使用现有 `/api/graph/*`
  - 工作台页面继续使用 `/api/ai/workbench/dispatch` 和 `/api/agent-runtime/*`

- 回归：
  - 不允许 graph 组件再次成为孤立文件
  - 不允许 `AIAssistant.vue` 被改回旧控制台多标签结构

## 实施顺序

1. 先修复当前 merge 中 AI workbench 的后端判路回归
2. 新增智能域壳层和图谱页路由
3. 挂载 graph workspace 页面
4. 补结构测试和路由测试
5. 最后再做一次 focused verification

## 成功标准

满足以下条件才算完成：

- 当前 `AI 助手工作台` 可继续打开并运行
- 新的 `图谱智能` 页面可访问
- graph import / qa / strategy 至少具备页面入口和 API 连通性
- 智能域内两个版本都不是孤立代码
- 当前主工作台的视觉和交互原则不被破坏

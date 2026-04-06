# App Sidebar Entry-First Design

## Goal

把控制台左侧边栏收紧成“入口优先”的结构：顶部只保留品牌与一条导入摘要，中部把空间让给分类导航，底部只保留时间。运行态信息不能再抢占主导航空间。

## Confirmed Outcome

边栏固定为三段：

1. `Brand Header`
   - 显示 Logo、平台标题。
   - 标题下只保留一条极简摘要，例如 `SSH Linux · 已导入 4 张卡`。
   - 摘要允许自然换行，不做截断。

2. `Grouped Nav Rail`
   - 主体必须是页面入口，不再放大块状态面板。
   - 使用分类 tab 切换入口组：
     - `治理`：`总览 / 任务 / 调度`
     - `分析`：`能耗 / 观察 / 告警`
     - `支持`：`智能`
   - 当前分类只显示对应入口组，导航区独立滚动。

3. `Minimal Footer`
   - 底部只显示 `时间`。
   - 不再保留 `运行台 / 桌面端` tab、状态条、更新按钮、环境事实卡。

## Problems Being Solved

1. 旧边栏把运行状态、桌面信息、来源说明堆进侧边栏，主导航被压缩。
2. 入口列表过长，视觉重点不在页面切换，而在状态堆叠。
3. 信息 dock 与导航互相争抢高度，调一处会牵连整体布局。
4. 旧设计虽然信息多，但不利于快速进入治理页面。

## Data Mapping

现有数据足够，不新增接口：

- `appInfo.connectionModeLabel` 或导入来源信息，用于摘要里的来源文案。
- `store.importContext.imported_gpu_indexes`，用于摘要里的导入卡数。
- `currentPath`，用于确定当前激活分组与激活入口。
- `currentTime`，用于底部时间显示。

## Component Boundaries

- `AppPrimarySidebar.vue`
  - 只负责三段式骨架与 props 分发。
- `SidebarBrandCard.vue`
  - 只负责品牌区与摘要。
- `SidebarNavRail.vue`
  - 只负责分类 tab、入口过滤、激活态与锁定态。
- `SidebarInfoDock.vue`
  - 收缩为极简底部时间组件，保留文件名但不再承担信息面板职责。

## Layout Rules

1. 外层保持 `grid-template-rows: auto minmax(0, 1fr) auto`。
2. 中部导航区单独滚动，头部与底部固定，不因内容增减位移。
3. 说明文字允许换行，禁止 `ellipsis` 截断。
4. 不使用绝对定位、负 margin 或高度联动技巧去“挤”出空间。
5. 视觉密度通过分组和节奏控制，而不是继续堆更多小卡片。

## Verification Targets

1. 结构测试应断言分类 tab 为 `治理 / 分析 / 支持`。
2. 结构测试应断言导航只按当前分组显示入口。
3. 结构测试应断言顶部只保留单条摘要，底部只保留时间。
4. 结构测试应明确移除旧的 `运行台 / 桌面端` dock 断言。
5. 前端构建必须保持通过。

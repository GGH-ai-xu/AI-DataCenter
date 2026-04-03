# App Sidebar Information Rail Redesign

## Goal

重构控制台左侧主边栏，让它在窄宽度下仍然保持高信息密度、清晰层级和稳定布局，避免当前“导航卡片 + 底部信息卡片连续堆叠”的拥挤感。

## Problems To Solve

1. 主导航、运行状态、环境来源、桌面动作、时钟被平铺在同一列，视觉上没有主次。
2. 底部信息模块彼此没有分类，导致用户必须扫描整段内容才能找到连接状态或导入范围。
3. 侧边栏在窄宽度下会形成连续大卡片，垂直节奏过重，信息密集但不紧凑。
4. 现有 footer 结构高度联动明显，一个区域变高会挤压其他区域，容易造成整体失衡。

## Scope

本次只重构控制台左侧边栏及其直接依赖的前端结构：

- `frontend/src/components/app/AppPrimarySidebar.vue`
- 新增边栏子组件与样式拆分
- 如有必要，调整 `frontend/src/App.vue` 的 sidebar 传参与数据组织

不修改路由逻辑、不改变控制台业务功能、不新增后端接口。

## Proposed Structure

边栏改为三段式稳定布局：

1. `Brand Header`
   - 一张紧凑头部卡，保留 Logo、平台标题、副标题。
   - 标题允许自然换行，不做截断。
   - 副标题缩短成辅助信息，不再承担状态说明。

2. `Primary Nav Rail`
   - 保持主导航固定可见，不改成 tab。
   - 导航按钮从“厚卡片”改成“紧凑轨道项”：图章、标题、说明三段式。
   - 每项独立高度与内边距固定，说明文本允许换行但不得溢出。

3. `Info Dock`
   - 底部改成一个统一的信息面板，内部使用 tab 分类。
   - 默认两个 tab：
     - `运行台`：导入来源、前后端来源、导入范围、运行时状态、实时通道状态。
     - `桌面端`：版本、更新按钮、桌面运行信息；仅桌面环境显示。
   - 时钟与在线状态收口为面板底部状态条，不再单独占两张卡。

## Component Boundaries

- `AppPrimarySidebar.vue`
  - 负责整体网格骨架与 props 分发。
- `SidebarBrandCard.vue`
  - 只负责品牌头部展示。
- `SidebarNavRail.vue`
  - 只负责导航项渲染与选中/锁定态。
- `SidebarInfoDock.vue`
  - 只负责 tab、环境信息、状态条、桌面动作。

这样可以把视觉块与交互块分离，避免某一块调整后牵动全部布局。

## Layout Rules

1. 外层边栏继续使用 `grid-template-rows: auto minmax(0, 1fr) auto`，但每个区域内部独立滚动，不共享高度。
2. `Nav Rail` 只承担导航滚动；`Info Dock` 自身固定高度并内部滚动，不挤压导航。
3. 不使用绝对定位、不使用负 margin、不依赖内容高度去对齐其他区块。
4. 所有标题、标签、说明默认允许换行，禁止通过 `ellipsis` 隐藏信息。
5. 视觉密度通过更紧凑的卡片内边距、分组标题、状态条实现，而不是减少信息。

## Visual Direction

- 保留当前米白 + 墨绿 + 朱砂印章语言，不改整体品牌方向。
- 导航区强调“主工作流”，信息区强调“运行上下文”。
- 卡片数量减少，但层次更强：头部 1 块、导航 1 块、信息面板 1 块。
- tab 栏要轻量，不做重色大按钮，重点放在内容分组而不是装饰。

## Data Mapping

现有 `appInfo`、`runtimeStatus`、`workspaceLocked`、`wsConnected`、`currentTime` 继续复用，不新增后端字段。

推荐在边栏内部将这些 props 重新组织为两类数据：

- `runtimePanelItems`
  - 导入模式、前端来源、后端来源、导入范围、对照网页
- `desktopPanelItems`
  - 版本、更新动作、桌面运行说明

这样可以降低 `App.vue` 与具体布局之间的耦合。

## Verification

实现阶段至少验证以下内容：

1. 窄宽度下边栏没有文字截断、组件截断、重叠覆盖。
2. 导航区与信息区互不牵连，切换 tab 不影响导航布局。
3. `workspaceLocked`、`runtimeStatus`、`wsConnected` 的状态在新布局下仍能正确展示。
4. 桌面模式与网页模式都能正常渲染，桌面 tab 在网页环境下自动隐藏。
5. 更新 `tests/test_frontend_ui_structure.py`，增加侧边栏分区与 tab 结构断言。

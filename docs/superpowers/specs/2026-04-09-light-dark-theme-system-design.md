# 明暗主题切换设计

日期：2026-04-09

## 背景

当前前端只有一套深色主题，视觉 token 主要集中在 [frontend/src/style.css](/mnt/e/code/ai-datacenter/frontend/src/style.css)。

但主题结构并不完全统一：

- 全局页面大多依赖 `--bg-*`、`--text-*`、`--accent-*` 这套语义 token
- 控制台壳层 [frontend/src/views/ConsoleShell.vue](/mnt/e/code/ai-datacenter/frontend/src/views/ConsoleShell.vue) 又额外定义了一套写死的 `--console-*` 颜色
- 登录页、改密页、侧栏等少量区域仍存在直接写死的深色背景和亮色文字渐变

这会导致一个明显风险：如果只在全局样式里补亮色 token，而不处理控制台壳层和局部硬编码，最终会出现“部分页面变亮、壳层仍然发黑、个别标题看不清”的半切换状态。

用户目标不是给项目补一个形式上的开关，而是：

- 提供白天/黑夜两套可用主题
- 支持跟随系统
- 允许用户手动覆盖
- 保持当前产品的克制、专业、偏产品化界面质感，而不是退化成普通白底后台

## 目标

本次设计的目标如下：

- 建立统一的全局主题系统，支持 `system / dark / light` 三态偏好
- 让主题切换成为全平台级能力，而不是零散页面自管
- 让根节点、控制台壳层、侧栏、登录页和六个一级页面在主题切换时保持一致
- 保留现有品牌气质，亮色主题与深色主题形成同一产品家族，而不是两套风格割裂的界面
- 为后续页面继续收口样式提供稳定的语义 token 基础

## 非目标

本次不做以下事项：

- 不引入第三套“自动高对比度”或其它辅助主题
- 不为旧浏览器补兼容分支
- 不新增复杂主题编辑器、配色面板或自定义品牌色功能
- 不重做六个一级页面的信息架构
- 不把这次工作扩展为全面视觉翻新项目

## 用户确认的设计结论

### 1. 主题行为

用户已确认主题行为为：

- 跟随系统并允许手动覆盖

这意味着主题偏好必须是三态，而不是简单的深浅布尔开关：

- `system`
- `dark`
- `light`

### 2. 视觉方向

用户已确认亮色主题继续保留当前产品气质：

- 不做纯白后台
- 保留层次感、轻玻璃感和产品化控制台观感
- 继续沿用现有蓝系品牌强调色

### 3. 开关位置

用户已确认主题开关应作为全局能力放在控制台壳层，并采用：

- 展开侧栏时显示完整三态切换控件
- 收起侧栏时收成单图标入口，再展开小浮层菜单

### 4. 落地范围

用户已确认第一阶段必须覆盖：

- 全局样式
- App 根层
- 全局 store
- ConsoleShell
- 左侧边栏
- 登录页与改密页
- 六个一级页面及近期重点工作台页

## 总体方案

本次采用“单一真源 + 双层 token”的主题方案。

核心思想：

1. 主题状态只有一个真源  
   使用全局 store 维护主题偏好和解析后的最终主题。

2. 根节点只有一个主题标记  
   最终主题只写入 `document.documentElement.dataset.theme`。

3. 所有视觉样式最终都回收到语义 token  
   控制台壳层、登录页、侧栏等局部样式可以保留各自的层次 token，但这些 token 只能映射全局语义 token，不能继续写死深色值。

这套方案优于“全局一套、控制台再单独补一套亮色变量”的原因是：

- 状态更简单
- 后续维护成本更低
- 页面之间不会出现主题割裂
- 后续重构组件时不需要再次处理深浅主题分叉

## 主题状态模型

### 状态定义

在 [frontend/src/stores/app.js](/mnt/e/code/ai-datacenter/frontend/src/stores/app.js) 中新增以下状态：

- `themePreference`: `system | dark | light`
- `resolvedTheme`: `dark | light`

推荐增加的 action：

- `hydrateThemePreference()`
- `setThemePreference(nextPreference)`
- `syncResolvedTheme()`

推荐增加的 getter / computed：

- `isSystemTheme`
- `isDarkTheme`
- `isLightTheme`

### 解析规则

最终主题解析规则固定为：

1. `themePreference === 'dark'` 时，`resolvedTheme = 'dark'`
2. `themePreference === 'light'` 时，`resolvedTheme = 'light'`
3. `themePreference === 'system'` 时，读取 `window.matchMedia('(prefers-color-scheme: dark)')`

### 持久化策略

主题偏好需要持久化到本地存储。

推荐 key：

- `ai-datacenter-theme-preference`

保存内容只记录用户偏好，不记录 `resolvedTheme`，因为最终主题始终可以重新解析。

### 系统主题监听

当用户偏好为 `system` 时，应用需要持续监听系统主题变化，并自动重新计算 `resolvedTheme`。

约束：

- 只有 `system` 模式才响应系统变化
- 用户手动选了 `dark` 或 `light` 后，系统变化不得覆盖用户显式选择

## 根节点同步机制

### DOM 写入目标

最终主题需要同步到 `document.documentElement`：

- `data-theme="dark" | "light"`

同时同步：

- `color-scheme: dark | light`

### 推荐实现边界

推荐将 DOM 同步逻辑抽到独立模块，而不是直接散落在组件里。

建议新增：

- [frontend/src/lib/themeMode.js](/mnt/e/code/ai-datacenter/frontend/src/lib/themeMode.js)

职责：

- 读取和校验主题偏好
- 解析系统主题
- 绑定和解绑系统主题监听
- 将最终主题写入根节点

[frontend/src/App.vue](/mnt/e/code/ai-datacenter/frontend/src/App.vue) 只负责在应用启动时初始化主题同步，不负责维护主题业务逻辑。

## Token 分层

### 第一层：全局语义 token

在 [frontend/src/style.css](/mnt/e/code/ai-datacenter/frontend/src/style.css) 中建立双套主题值：

- `:root[data-theme='dark']`
- `:root[data-theme='light']`

这一层负责定义所有全局语义 token，例如：

- `--bg-base`
- `--bg-card`
- `--bg-card-hover`
- `--bg-surface`
- `--text-primary`
- `--text-secondary`
- `--text-muted`
- `--border-color`
- `--border-strong`
- `--shadow-card`
- `--shadow-hover`
- `--accent-primary`
- `--accent-warning`
- `--accent-danger`

### 第二层：域内 token

局部页面可以保留自己的域内 token，例如：

- `--console-*`
- `--import-*`
- `--energy-*`

但这些 token 不能继续写具体颜色值，而必须映射到全局语义 token，例如：

- `--console-text: var(--text-primary)`
- `--console-panel: var(--bg-card)`
- `--console-border: var(--border-color)`

允许域内 token对全局 token做少量偏移，例如更深一层边框或更弱一层背景，但这种偏移也必须同时有深浅两态来源，不能写死“永远深色”的值。

## 亮色主题视觉规范

### 基底

亮色主题不使用纯白。

推荐方向：

- 页面基底：暖白偏冷灰
- 卡片层：轻玻璃 / 轻磨砂
- 强调边框：弱蓝灰
- 阴影：短、轻、克制

### 背景系统

当前 `body` 与 `body::before / ::after` 的背景层次较依赖深色场景，因此需要变量化：

- 主背景渐变
- 柔光氛围层
- 网格 / 噪点层
- 选区颜色
- 滚动条颜色

推荐在 [frontend/src/style.css](/mnt/e/code/ai-datacenter/frontend/src/style.css) 中增加背景相关 token，例如：

- `--app-body-background`
- `--app-body-glow`
- `--app-body-grid-opacity`
- `--selection-bg`
- `--scrollbar-thumb`

### 文本与强调色

亮色主题继续保留品牌蓝作为主强调色，不改品牌色相。

要求：

- 深色主题的高亮蓝在亮色主题下适当收敛，避免发荧光
- 危险色与告警色在亮色主题下降低刺眼程度
- 标题渐变必须改为 theme-aware 变量，不能继续直接用白色渐变

## 壳层与页面迁移规则

### ConsoleShell

[frontend/src/views/ConsoleShell.vue](/mnt/e/code/ai-datacenter/frontend/src/views/ConsoleShell.vue) 是本次迁移的关键点。

改造要求：

- 现有 `--console-*` 不再写死深色值
- 壳层背景、卡片面、边框、文字全部回收到语义 token
- 壳层仍然允许比普通页面更“收敛、更控制台化”，但这种差异只能通过映射实现

### 侧栏

相关组件：

- [frontend/src/components/app/AppPrimarySidebar.vue](/mnt/e/code/ai-datacenter/frontend/src/components/app/AppPrimarySidebar.vue)
- [frontend/src/components/app/SidebarBrandCard.vue](/mnt/e/code/ai-datacenter/frontend/src/components/app/SidebarBrandCard.vue)
- [frontend/src/components/app/SidebarNavRail.vue](/mnt/e/code/ai-datacenter/frontend/src/components/app/SidebarNavRail.vue)

要求：

- 删除组件内部与深色绑定过强的写死背景值
- 侧栏面板、切换服务器按钮、收起按钮都必须跟随语义 token
- 新增主题切换入口，并在展开态与折叠态下分别有稳定表现

### 登录页与改密页

相关页面：

- [frontend/src/views/LoginView.vue](/mnt/e/code/ai-datacenter/frontend/src/views/LoginView.vue)
- [frontend/src/views/ChangePasswordView.vue](/mnt/e/code/ai-datacenter/frontend/src/views/ChangePasswordView.vue)

要求：

- hero 标题渐变改为主题变量驱动
- 卡片背景与信息卡边框不再依赖深色假设
- 表单输入、错误态、说明文字在浅底下保持足够对比度

### 六个一级页面

覆盖：

- 总览
- 治理
- 能耗
- 观察
- 告警
- 智能

要求：

- 优先依赖全局 token 自动吃到主题
- 对少量写死颜色的局部点位进行扫尾修正
- 不要求本轮重做页面布局，只修复主题不适配问题

## 主题切换入口设计

### 展开态

展开态下，主题开关放在左侧边栏底部区域，靠近“收起导航”控制。

推荐控件：

- 三态 segmented control
- 文案为：`系统 / 深色 / 亮色`

要求：

- 视觉上比主按钮更轻，不应抢过导航和切换服务器按钮
- 当前选中状态要有清晰但克制的高亮

### 折叠态

折叠态下，不保留完整三态控件。

改为：

- 单个主题图标按钮
- 点击后弹出小型菜单
- 菜单中显示：`系统 / 深色 / 亮色`

这样可以避免折叠态侧栏出现挤压、错位或过宽文本。

### 移动端

移动端不增加单独大卡。

推荐放在移动壳层现有操作区，以小图标入口或轻量文本按钮承接，保持它作为全局偏好设置的属性，而不是页面内容的一部分。

## 模块拆分建议

为避免把主题逻辑继续堆进现有大文件，推荐拆分为以下责任边界：

### `frontend/src/lib/themeMode.js`

职责：

- 主题偏好常量
- 偏好校验
- 系统主题解析
- 本地存储读写
- DOM 同步

### `frontend/src/components/app/ThemeModeSwitch.vue`

职责：

- 三态切换 UI
- 支持常规模式与折叠模式
- 只负责展示与事件抛出，不直接读写 DOM

### `frontend/src/stores/app.js`

职责：

- 保存主题偏好状态
- 暴露设置动作
- 持有 `resolvedTheme`

### `frontend/src/App.vue`

职责：

- 启动时初始化主题
- 应用销毁时解绑系统主题监听

这种拆分的好处是：

- 避免 `app.js` 继续膨胀
- 让主题 UI 与主题状态解耦
- 后续如果把主题开关放到其它位置，不需要改主题核心逻辑

## 数据流

主题切换数据流固定如下：

1. 应用启动
2. 从本地存储读取 `themePreference`
3. 结合系统主题解析 `resolvedTheme`
4. 把最终主题写入根节点 `data-theme`
5. 所有页面通过 token 自动响应
6. 用户切换主题
7. 更新 store 状态
8. 写回本地存储
9. 同步根节点
10. 页面即时刷新视觉状态，无需刷新路由

## 错误处理原则

本项目已明确不接受为了“看起来能跑”而加入静默降级。

因此本次主题系统采用以下原则：

- 只面向现代运行环境，不补旧浏览器兼容分支
- 主题偏好必须经过显式校验，非法值直接回退到 `system`
- 若本地存储写入失败，必须显式记录错误，不做无提示吞掉
- 若 DOM 同步失败，应保留明确错误日志，便于定位

这里的“回退到 `system`”属于输入校验的确定性行为，而不是运行期隐藏失败的降级路径。

## 验证标准

### 功能验证

- 用户可在 `系统 / 深色 / 亮色` 三态之间切换
- 手动切换后无需刷新页面立即生效
- 用户选择 `system` 时，系统主题变化后界面自动跟随
- 用户选择 `dark/light` 时，系统主题变化不得覆盖用户偏好

### 一致性验证

- 登录页、改密页、导入层、控制台壳层、六个一级页面都能稳定切换
- 侧栏展开态和折叠态下都能操作主题入口
- 不出现深色页残留在亮色壳层中的混搭状态
- 不出现亮色背景下低对比度文字或丢失边框

### 结构验证

建议补充结构测试，至少断言：

- [frontend/src/style.css](/mnt/e/code/ai-datacenter/frontend/src/style.css) 存在 `:root[data-theme='light']`
- [frontend/src/stores/app.js](/mnt/e/code/ai-datacenter/frontend/src/stores/app.js) 存在主题偏好状态与设置 action
- 壳层中存在主题切换入口组件
- 根层存在主题初始化逻辑

### 本地验证

继续沿用当前仓库约束：

- 不依赖 `vite build`
- 以结构测试、目标文件解析和局部回归验证为主

## 实施顺序

推荐按以下顺序实施：

1. 在 `style.css` 建立深浅双套主题语义 token
2. 新增 `themeMode` 核心模块
3. 在 `app.js` 接入主题偏好状态
4. 在 `App.vue` 完成启动时初始化与监听注册
5. 将 `ConsoleShell.vue` 的 `--console-*` 改为语义映射
6. 新增侧栏主题切换入口
7. 扫描登录页、改密页、导入页、六个一级页面中的写死颜色并修正
8. 补结构测试与解析验证

## 范围控制

为了把这次工作控制在单次实现周期内，本轮应聚焦：

- 明暗主题底层能力
- 全局入口
- 一致性修复

不把本轮扩展成：

- 页面重构
- 样式大清洗
- 主题自定义系统

## 规格自检

已检查以下事项：

- 无 `TODO`、`TBD` 或占位描述
- 主题行为、开关位置、视觉方向与用户确认一致
- 架构、迁移范围、验证标准之间无冲突
- 范围聚焦在一次实现计划可承载的规模内

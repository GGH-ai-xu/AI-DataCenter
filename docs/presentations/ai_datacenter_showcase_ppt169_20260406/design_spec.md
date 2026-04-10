# AI DataCenter Showcase - Design Spec

## I. Project Information

| Item | Value |
| ---- | ----- |
| **Project Name** | AI DataCenter Showcase |
| **Canvas Format** | PPT 16:9 (1280x720) |
| **Page Count** | 25 |
| **Design Style** | Top Consulting |
| **Target Audience** | 投资人、技术评审、答辩老师 |
| **Use Case** | 项目路演、课程/比赛答辩、产品方案展示 |
| **Created Date** | 2026-04-06 |

---

## II. Canvas Specification

| Property | Value |
| -------- | ----- |
| **Format** | PPT 16:9 |
| **Dimensions** | 1280x720 |
| **viewBox** | `0 0 1280 720` |
| **Margins** | left/right 56px, top 44px, bottom 34px |
| **Content Area** | x=56~1224, y=108~670 |

---

## III. Visual Theme

### Theme Style

- **Style**: Top Consulting
- **Theme**: Light theme
- **Tone**: 专业、克制、科技、结论先行

### Color Scheme

| Role | HEX | Purpose |
| ---- | --- | ------- |
| **Background** | `#F7F9FB` | 页面主背景 |
| **Secondary bg** | `#EDF2F6` | 卡片、图表区块背景 |
| **Primary** | `#17313A` | 标题、深色强调、顶部细条 |
| **Accent** | `#19A38C` | 核心高亮、流程重点、正向状态 |
| **Secondary accent** | `#5B8DEF` | 技术结构、流程辅助高亮 |
| **Body text** | `#1F2937` | 正文 |
| **Secondary text** | `#5B6776` | 次级说明 |
| **Tertiary text** | `#8A94A3` | 页脚、标注 |
| **Border/divider** | `#D8E0E8` | 分隔线、边框 |
| **Success** | `#1F9D68` | 成功、成熟能力 |
| **Warning** | `#D9485F` | 风险、痛点、警示 |

### Gradient Scheme (if needed, using SVG syntax)

```xml
<linearGradient id="titleGradient" x1="0%" y1="0%" x2="100%" y2="0%">
  <stop offset="0%" stop-color="#17313A"/>
  <stop offset="100%" stop-color="#19A38C"/>
</linearGradient>

<radialGradient id="bgDecor" cx="82%" cy="12%" r="48%">
  <stop offset="0%" stop-color="#5B8DEF" stop-opacity="0.10"/>
  <stop offset="100%" stop-color="#5B8DEF" stop-opacity="0"/>
</radialGradient>
```

---

## IV. Typography System

### Font Plan

**Recommended preset**: P1

| Role | Chinese | English | Fallback |
| ---- | ------- | ------- | -------- |
| **Title** | Microsoft YaHei | Arial | SimHei |
| **Body** | Microsoft YaHei | Calibri | Arial |
| **Code** | Microsoft YaHei | Consolas | Monaco |
| **Emphasis** | SimHei | Arial Bold | Microsoft YaHei |

**Font stack**: `"Microsoft YaHei", "Arial", "Calibri", sans-serif`

### Font Size Hierarchy

**Baseline**: Body font size = 18px

| Purpose | Ratio | 24px baseline (relaxed) | 18px baseline (dense) | Weight |
| ------- | ----- | ---------------------- | -------------------- | ------ |
| Cover title | 2.5-3x | 60-72px | 45-54px | Bold |
| Chapter title | 2-2.5x | 48-60px | 36-45px | Bold |
| Content title | 1.5-2x | 36-48px | 27-36px | Bold |
| Subtitle | 1.2-1.5x | 29-36px | 22-27px | SemiBold |
| **Body content** | **1x** | **24px** | **18px** | Regular |
| Annotation | 0.75-0.85x | 18-20px | 14-15px | Regular |
| Page number/date | 0.55-0.65x | 13-16px | 10-12px | Regular |

---

## V. Layout Principles

### Page Structure

- **Header area**: 顶部 6px 渐变细条 + 44px 页标题区 + 46px takeaway box
- **Content area**: 主要图示、流程图、卡片、截图式 UI 区块
- **Footer area**: 来源、项目名、页码、`CONFIDENTIAL` 标识

### Common Layout Modes

| Mode | Suitable Scenarios |
| ---- | ----------------- |
| **Single column centered** | 封面、收束页、项目定义页 |
| **Left-right split (5:5)** | 场景对比、产品入口、角色与价值对照 |
| **Left-right split (4:6)** | 真实界面表达 + 结论解释 |
| **Top-bottom split** | 主流程、路线图、叙事推进 |
| **Three/four column cards** | 痛点、能力、优势、KPI 汇总 |
| **Matrix grid** | 竞争优势、接入模式、架构模块映射 |

### Spacing Specification

| Element | Recommended Range | Current Project |
| ------- | ---------------- | --------------- |
| Card gap | 20-32px | 24px |
| Content block gap | 24-40px | 28px |
| Card padding | 20-32px | 22px |
| Card border radius | 8-16px | 12px |
| Icon-text gap | 8-16px | 10px |
| Single-row card height | 530-600px | 548px |
| Double-row card height | 265-295px each | 272px |
| Three-column card width | 360-380px each | 368px |

---

## VI. Icon Usage Specification

### Source

- **Built-in icon library**: `templates/icons/`
- **Usage method**: Placeholder format `{{icon:icon-name}}`

### Recommended Icon List

| Purpose | Icon Path | Page |
| ------- | --------- | ---- |
| 平台用户 / 登录 | `{{icon:user}}` | Slide 08 |
| 组织 / 多角色 | `{{icon:users}}` | Slide 06, 21 |
| 目标与范围 | `{{icon:target}}` | Slide 12, 24 |
| 告警 / 风险 | `{{icon:triangle-exclamation}}` | Slide 04, 16 |
| 核心洞察 | `{{icon:lightbulb}}` | Slide 05, 24 |
| 流程箭头 | `{{icon:arrow-right}}` | Slide 07, 10 |
| 趋势 / 增长 | `{{icon:arrow-trend-up}}` | Slide 24 |
| 成功 / 可用 | `{{icon:circle-checkmark}}` | Slide 10, 13 |
| 配置 / 系统能力 | `{{icon:cog}}` | Slide 18, 23 |
| 图表 / 指标 | `{{icon:chart-bar}}` | Slide 15, 24 |
| 数据 / 状态 | `{{icon:database}}` | Slide 18, 19 |
| 文件 / 主机记录 | `{{icon:folder}}` | Slide 13 |
| 安全 / 权限 | `{{icon:shield}}` | Slide 21 |
| 凭据加密 | `{{icon:lock-closed}}` | Slide 22 |
| 主密钥 | `{{icon:key}}` | Slide 22 |
| 刷新 / 重连 | `{{icon:arrow-rotate-right}}` | Slide 20 |

---

## VII. Chart Reference List

| Chart Type | Reference Template | Used In |
| ---------- | ------------------ | ------- |
| `horizontal_bar_chart` | `templates/charts/horizontal_bar_chart.svg` | Slide 04 |
| `process_flow` | `templates/charts/process_flow.svg` | Slide 07 |
| `grouped_bar_chart` | `templates/charts/grouped_bar_chart.svg` | Slide 10 |
| `matrix_2x2` | `templates/charts/matrix_2x2.svg` | Slide 20 |
| `timeline` | `templates/charts/timeline.svg` | Slide 25 |
| `kpi_cards` | `templates/charts/kpi_cards.svg` | Slide 24 |

---

## VIII. Image Resource List

| Filename | Dimensions | Ratio | Purpose | Type | Status | Generation Description |
| -------- | --------- | ----- | ------- | ---- | ------ | --------------------- |
| `login_view_placeholder.png` | 1280x720 | 1.78 | 登录页产品证据位 | Diagram | Placeholder | 用浅底界面框表达用户名密码登录、首登改密提示与角色入口，不使用真实位图 |
| `import_workspace_placeholder.png` | 1280x720 | 1.78 | 导入准备页证据位 | Diagram | Placeholder | 表达已保存主机、连接来源、硬件概览、选卡导入四阶段的产品入口结构 |
| `hardware_scan_placeholder.png` | 1280x720 | 1.78 | 硬件扫描与选卡证据位 | Diagram | Placeholder | 表达 CPU/GPU 扫描摘要、卡片状态、选卡区块 |
| `saved_hosts_placeholder.png` | 1280x720 | 1.78 | 已保存主机复用证据位 | Diagram | Placeholder | 表达主机卡片、扫描并继续、权限范围与凭据复用状态 |
| `console_placeholder.png` | 1280x720 | 1.78 | 控制台总览证据位 | Diagram | Placeholder | 表达左侧导航、监控主区、运行台摘要和多模块入口 |
| `governance_placeholder.png` | 1280x720 | 1.78 | 监控治理联动证据位 | Diagram | Placeholder | 表达告警、任务、治理动作、状态变化的闭环面板 |
| `desktop_shell_placeholder.png` | 1280x720 | 1.78 | 桌面壳交付证据位 | Diagram | Placeholder | 表达 Electron 壳、启动器、前后端协同运行的桌面交付形态 |

**Status descriptions**:

- **Pending** - Needs AI generation, provide detailed description
- **Existing** - User already has image, place in `images/`
- **Placeholder** - Not yet processed, use dashed border placeholder in SVG

---

## IX. Content Outline

### Part 1: 问题定义与项目定题

#### Slide 01 - 封面

- **Layout**: Full-screen clean background + centered title + bottom metadata
- **Title**: AI DataCenter
- **Subtitle**: 智算中心优化代码生成系统
- **Info**: 产品展示 / 答辩稿 | 2026.04

#### Slide 02 - 一句话项目定义

- **Layout**: Single column centered + 3 supporting cards
- **Title**: 这不是一个“看 GPU 数据”的页面，而是智算中心优化代码生成系统
- **Content**:
  - 平台先登录，再进入独立导入层
  - 导入前先扫描硬件并确认治理范围
  - 控制台只显示和治理本次导入的 GPU

#### Slide 03 - 行业背景与问题

- **Layout**: Left-right split (4:6)
- **Title**: 共享 GPU 场景正在普及，但资源使用和治理方式仍停留在脚本时代
- **Content**:
  - 实验室、企业研发、共享服务器的 GPU 使用者不断增多
  - 运维、算法、管理三类角色对资源状态的视角割裂
  - 现有方式缺乏统一入口、统一范围和统一复盘

#### Slide 04 - 现有方案痛点

- **Layout**: Top takeaway + 4 pain-point cards + ranking style comparison
- **Title**: 传统 SSH、脚本和零散监控页能“看到资源”，但很难真正治理资源
- **Chart**: `horizontal_bar_chart`
- **Content**:
  - 信息分散：看监控、连主机、管进程分属不同入口
  - 边界模糊：控制台常混入不属于本次任务的 GPU
  - 安全薄弱：凭据复用、权限边界、用户隔离不足
  - 复盘困难：缺乏任务、告警、调度的一体化观察

#### Slide 05 - 我们的解决思路

- **Layout**: Hero statement + capability map
- **Title**: 平台以“登录 + 导入 + 选卡 + 控制台”重构共享 GPU 的治理闭环
- **Content**:
  - 平台身份先于机器连接
  - 导入层先于控制台
  - 范围控制先于治理动作
  - 治理与监控、告警、任务共同形成闭环

### Part 2: 场景、角色与产品流程

#### Slide 06 - 目标用户与使用场景

- **Layout**: Four-column persona cards
- **Title**: 同一平台同时服务管理员、实验室负责人和实际用卡人员
- **Content**:
  - 管理员：统一接入、用户管理、主机记录与权限可见范围
  - 实验室负责人：看整体资源情况与风险
  - 算法工程师：导入自己需要治理的 GPU
  - 项目答辩/展示者：用统一界面表达系统能力与交付完成度

#### Slide 07 - 产品主流程总览

- **Layout**: Horizontal process flow with six stages
- **Title**: 用户使用路径被明确收敛为六个稳定步骤，而不是进入控制台后再临时切换连接
- **Chart**: `process_flow`
- **Content**:
  - 登录
  - 进入导入准备页
  - 选择连接来源或已保存主机
  - 扫描目标机器硬件
  - 选择本次纳入治理的 GPU
  - 进入控制台持续监控与治理

#### Slide 08 - 登录与权限入口

- **Layout**: Left screenshot-style panel + right explanation stack
- **Title**: 平台先建立用户身份，再决定谁可以看到哪些主机和资源
- **Content**:
  - 默认管理员首次启动自动创建
  - 首次登录要求改密
  - 管理员可见全部用户的主机记录
  - 普通用户只可见自己的连接历史和主机记录

#### Slide 09 - 导入准备页设计

- **Layout**: Large UI reconstruction + bottom three value points
- **Title**: 控制台前置了一个独立准备页，把接入逻辑从管理逻辑中彻底剥离
- **Content**:
  - 已保存主机
  - 连接来源
  - 硬件概览
  - 选卡导入

#### Slide 10 - 多源接入能力

- **Layout**: Three-column comparison matrix
- **Title**: 平台支持本机 Agent、远程 Agent 与 SSH Linux 三种接入模式
- **Chart**: `grouped_bar_chart`
- **Content**:
  - 本机 Agent：面向当前机器本地采集
  - 远程 Agent：面向目标机已部署 agent 的场景
  - SSH Linux：目标机不运行 agent，也可直接接入
  - 从产品视角统一表现为一次扫描与一次导入

### Part 3: 核心产品能力

#### Slide 11 - 硬件扫描与导入确认

- **Layout**: Main UI reconstruction + right-side insight cards
- **Title**: 用户在进入控制台前就能看到 CPU、GPU 与当前卡状态，并明确导入范围
- **Content**:
  - 展示 CPU、内存、GPU 温度、功耗、利用率
  - 支持看到当前候选卡池
  - 扫描结果直接进入下一步选卡导入

#### Slide 12 - 只治理本次导入 GPU

- **Layout**: Before/after scope diagram
- **Title**: 平台最核心的边界设计，是控制台只治理“本次导入选中的卡”
- **Content**:
  - 避免无关资源进入治理视图
  - 避免误操作其他人任务所在 GPU
  - 让责任、范围、动作保持一致

#### Slide 13 - 已保存主机与自动复用

- **Layout**: Left saved-host cards + right workflow explanation
- **Title**: 成功连接过的主机会被加密保存，后续可直接“扫描并继续”
- **Content**:
  - 记录主机标签、地址、用户、认证方式和 owner
  - 支持凭据复用和凭据失效后的显式恢复
  - 减少重复录入 SSH 密码或私钥

#### Slide 14 - 控制台能力总览

- **Layout**: Full-width console reconstruction + labeled hotspots
- **Title**: 一旦导入完成，控制台就只负责治理和监控，不再承载连接切换逻辑
- **Content**:
  - Dashboard
  - Monitor Center
  - Task Manager
  - Alert Center
  - Scheduler
  - AI Assistant

#### Slide 15 - 监控与治理一体化

- **Layout**: Two-column closed-loop diagram
- **Title**: 平台不仅能看状态，还能围绕状态直接执行治理动作
- **Content**:
  - 从 GPU、系统、进程状态识别问题
  - 直接执行功耗、任务与进程治理动作
  - 形成“发现问题 -> 发起动作 -> 观察结果”的闭环

#### Slide 16 - 告警、任务与调度

- **Layout**: Three workbench cards
- **Title**: 告警、任务与调度构成了治理平台的运营层，而不是附属页面
- **Content**:
  - 告警中心：实时流、今日记录、历史归档
  - 任务管理：训练任务与进程状态观测
  - 调度与能耗：功耗/策略层面的长期优化空间

#### Slide 17 - 桌面壳与部署形态

- **Layout**: Left product shell illustration + right deployment list
- **Title**: 平台不仅可在浏览器运行，也支持通过 Electron 桌面壳进行本地交付
- **Content**:
  - 前端、后端、agent 由脚本统一拉起
  - 支持 Windows 开发与桌面交付
  - 有利于实验室或内网环境的本地部署

### Part 4: 技术实现与系统可信度

#### Slide 18 - 系统总体架构

- **Layout**: Layered architecture diagram
- **Title**: 系统采用“前端 + 后端 + 采集/控制 Agent + 桌面壳”的分层架构
- **Content**:
  - Vue 3 + Vite 前端
  - FastAPI 后端
  - server-agent 负责主机侧采集与控制
  - Electron 封装桌面运行形态

#### Slide 19 - 导入层与运行时架构

- **Layout**: State flow diagram
- **Title**: 导入层不是一个页面装饰，而是运行时范围控制的入口
- **Content**:
  - import context 持久化当前导入状态
  - provider_type 统一表达接入来源
  - imported_gpu_indexes 驱动后续控制台过滤
  - 控制台只消费过滤后的 GPU 与进程数据

#### Slide 20 - 双接入模型：Agent + SSH Linux

- **Layout**: Two-track architecture comparison
- **Title**: 平台同时支持目标机部署 Agent 和不部署 Agent 的 SSH Linux 接入
- **Chart**: `matrix_2x2`
- **Content**:
  - Agent 模式适合长期驻留采集和 HTTP 接入
  - SSH Linux 模式适合轻接入、零部署场景
  - 两种模式在前端被抽象成同一套导入和治理语义

#### Slide 21 - 登录、会话与权限隔离

- **Layout**: Identity boundary diagram + permission table
- **Title**: 平台登录与目标主机 SSH 认证是两条独立链路，权限边界清晰
- **Content**:
  - 平台用户基于用户名密码登录
  - 平台会话用于 API 鉴权
  - 目标主机仍通过 SSH 密码或私钥认证
  - 管理员与普通用户的主机可见范围不同

#### Slide 22 - 凭据安全与主密钥机制

- **Layout**: Encryption pipeline diagram
- **Title**: SSH 密码、私钥和 sudo 密码不会明文保存，而是由主密钥进行加密保护
- **Content**:
  - 主密钥只由平台启动环境提供
  - 凭据加密后保存，供后续自动重连
  - 主密钥失效或缺失时显式报错，不做静默降级

#### Slide 23 - 工程化与稳定性保障

- **Layout**: Four-pillar card layout
- **Title**: 为了从 demo 走向可交付系统，项目补齐了脚本、测试和进程治理链路
- **Content**:
  - `start-dev.bat` 自动清理旧进程并拉起三类服务
  - `install-deps.bat` 处理 `.venv` 占用与依赖安装
  - 前端 `npm test`、`npm run build` 与根级 `unittest`
  - Windows 环境优先的开发、运行和打包链路

### Part 5: 项目价值与未来空间

#### Slide 24 - 项目成果与竞争优势

- **Layout**: KPI cards + advantage matrix
- **Title**: 当前成果已经形成产品边界、技术边界和工程边界三重优势
- **Chart**: `kpi_cards`
- **Content**:
  - 产品边界：登录、导入、治理清晰分层
  - 技术边界：Agent/SSH 双接入 + runtime scope
  - 安全边界：平台用户隔离 + 主密钥凭据保护
  - 工程边界：脚本、测试、桌面化交付

#### Slide 25 - 未来规划与结束页

- **Layout**: Timeline + closing statement
- **Title**: 在当前能力基础上，平台可继续向多机、多协议和智能调度演进
- **Chart**: `timeline`
- **Content**:
  - 下一步：多机接入与组织级资源视图
  - 中期：更多远程协议与治理动作扩展
  - 长期：智能调度、策略推荐、资源画像与组织运营能力

---

## X. Speaker Notes Requirements

Generate corresponding speaker note files for each page, saved to the `notes/` directory:

- **File naming**: Match SVG names, e.g., `01_封面.md`
- **Content includes**: Script key points, timing cues, transition phrases
- **Total presentation duration**: 18-22 minutes
- **Notes style**: 正式、结论先行、适合答辩口播
- **Presentation purpose**: inform + persuade

---

## XI. Technical Constraints Reminder

### SVG Generation Must Follow:

1. viewBox: `0 0 1280 720`
2. Background uses `<rect>` elements
3. Text wrapping uses `<tspan>` (`<foreignObject>` FORBIDDEN)
4. Transparency uses `fill-opacity` / `stroke-opacity`; `rgba()` FORBIDDEN
5. FORBIDDEN: `clipPath`, `mask`, `<style>`, `class`, `foreignObject`
6. FORBIDDEN: `textPath`, `animate*`, `script`, `marker`/`marker-end`
7. Arrows use `<polygon>` triangles instead of `<marker>`
8. Logically related elements must be wrapped with `<g>`

### PPT Compatibility Rules:

- `<g opacity="...">` FORBIDDEN (group opacity); set on each child element individually
- Image transparency uses overlay mask layer (`<rect fill="bg-color" opacity="0.x"/>`)
- Inline styles only; external CSS and `@font-face` FORBIDDEN

---

## XII. Design Checklist

### Pre-generation

- [x] Content fits page capacity
- [x] Page structure follows SCQA rhythm
- [x] Product pages and architecture pages are separated
- [x] Screenshot-like evidence pages use consistent placeholder strategy
- [x] Colors, fonts, and layout spacing are globally unified

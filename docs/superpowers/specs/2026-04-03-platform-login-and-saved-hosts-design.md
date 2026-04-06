# Platform Login And Saved Hosts Design

## Goal

为平台新增真实的用户登录能力，并把“已保存主机 + 加密 SSH 凭据复用”整合进导入层。用户登录后可以看到自己成功连接过的主机，管理员可以查看全部用户的主机记录，用户下次登录后可直接复用已保存凭据完成扫描与导入，无需再次输入 SSH 密码。

## Scope

本次设计覆盖以下范围：

- 平台账号登录、登出、改密、管理员创建用户与重置密码
- 基于平台会话的 API 鉴权
- 每用户主机记录与管理员全局可见能力
- 基于主密钥的 SSH 凭据加密存储与解密复用
- 登录页、首次改密页、导入页“已保存主机”入口

不包含完整的注册体系、找回密码流程、邮箱验证、MFA、JWT refresh 体系或更细粒度 RBAC。

## Problems To Solve

1. 当前系统没有真正的平台账号体系，只有静态 token 鉴权，无法表达“谁登录了平台”。
2. 用户成功连接过的 SSH 主机没有与平台用户建立明确归属关系。
3. 现有凭据存储是明文 JSON，不能满足“加密保存并在下次登录后免输密码复用”的要求。
4. 导入层只有“新建连接”，没有“已保存主机”的直接入口。
5. 管理员与普通用户对主机记录的可见范围没有权限边界。

## Confirmed Decisions

### Identity Boundary

- 平台登录认证与目标机器 SSH 认证是两条独立链路。
- 平台用户通过 `用户名 + 密码` 登录平台。
- 目标机器仍通过 `SSH password / private key` 连接。
- 控制台继续只管理“本次导入选中的卡”，不因为新增登录而改变导入范围语义。

### User Model

- 用户不能自助注册，只能由管理员手动创建。
- 首次启动时自动创建默认管理员账号，并要求其首次登录后强制改密。
- 角色先收敛为两类：
  - `admin`
  - `member`

### Host Visibility

- 普通用户只能查看和复用自己保存的主机。
- 管理员可以查看全部用户的主机记录。
- 管理员的“可见全部”不改变主机归属，主机仍然绑定其 owner 用户。

### Credential Persistence

- SSH 密码、私钥、私钥口令、sudo 密码必须加密后保存。
- 主密钥仅从平台启动环境读取，不写入源码、数据库或明文配置文件。
- 若主密钥缺失、格式不合法或无法解密，相关功能直接显式失败，不做静默降级。

## Architecture

系统拆为三条明确链路：

1. `平台身份链路`
   - 用户登录平台后获得平台会话。
   - 前端后续 API 请求使用该会话访问后端。

2. `主机记忆链路`
   - 成功导入 SSH 目标后，把目标主机元信息与 owner 用户关联保存。
   - 导入页优先展示当前用户的已保存主机。

3. `凭据复用链路`
   - 成功导入时，把 SSH 凭据通过主密钥加密后写入凭据仓库。
   - 下次用户登录后点击已保存主机，后端解密凭据并直接执行扫描或导入。

## Data Model

### `platform_users`

字段：

- `id`
- `username`
- `password_hash`
- `role`
- `must_change_password`
- `is_active`
- `created_at`
- `updated_at`
- `last_login_at`

约束：

- `username` 全局唯一
- `role` 只允许 `admin | member`
- 默认管理员初始化时 `must_change_password = 1`

### `platform_sessions`

字段：

- `id`
- `user_id`
- `session_token_hash`
- `expires_at`
- `created_at`
- `last_seen_at`
- `revoked_at`

约束：

- 前端只持有 token 原文
- 数据库只保存 token hash
- 会话支持过期和吊销

### `saved_hosts`

字段：

- `id`
- `owner_user_id`
- `label`
- `provider_type`
- `host`
- `port`
- `username`
- `auth_type`
- `sudo_enabled`
- `host_fingerprint`
- `credential_ref`
- `last_connected_at`
- `created_at`
- `updated_at`

说明：

- 主机表只保存目标元信息与凭据引用
- 凭据秘密内容不直接写进表中
- 同一用户可以保存多个主机

## Credential Storage

现有 `CredentialStore` 需要升级为“加密后持久化”的实现。

目标行为：

- 保存凭据时，对每个秘密字段加密后写入 JSON 仓库
- 读取凭据时，使用启动主密钥解密
- `masked_snapshot()` 仍只返回掩码视图
- 解密失败时抛显式错误，阻止继续扫描或导入

主密钥规则：

- 由平台启动环境变量提供
- 平台启动时验证其可用性
- 未配置主密钥时，涉及 SSH 凭据保存与复用的接口应返回明确错误

## Backend APIs

### Auth APIs

- `POST /api/auth/login`
  - 校验用户名和密码
  - 返回当前用户信息、session token、`must_change_password`

- `POST /api/auth/logout`
  - 吊销当前会话

- `GET /api/auth/me`
  - 返回当前登录用户
  - 供前端刷新后恢复登录态

- `POST /api/auth/change-password`
  - 当前用户修改密码
  - 首次默认管理员必须通过该接口完成改密

### Admin User APIs

- `GET /api/admin/users`
  - 管理员查看用户列表

- `POST /api/admin/users`
  - 管理员手动创建用户

- `POST /api/admin/users/{id}/reset-password`
  - 管理员重置用户密码
  - 可重新设置 `must_change_password`

### Saved Host APIs

- `GET /api/hosts`
  - 普通用户返回自己的主机
  - 管理员可带筛选条件查看全部主机

- `DELETE /api/hosts/{id}`
  - 删除主机记录和其凭据引用

### Import API Adjustments

现有导入接口保留，但增加“已保存主机复用”语义：

- `POST /api/system/import-context/scan`
- `POST /api/system/import-context`

新增行为：

- 通过新建 SSH 目标成功导入后，自动 upsert `saved_hosts`
- 通过已保存主机扫描时，可只传 `host_id`
- 后端按当前登录用户权限展开主机信息并解密凭据
- 若管理员访问他人主机记录，应保留 owner 信息但允许扫描

## Auth Middleware Strategy

现有静态 token 中间件升级为“平台会话优先”的鉴权流程。

目标顺序：

1. 优先解析平台 session
2. 解析成功则挂载当前平台用户与角色
3. 如无 session，可保留旧静态 token 作为兼容通道
4. 未认证请求按新规则拒绝或仅放行公开路径

首次管理员未改密时：

- 仅允许访问 `me / logout / change-password` 等必要接口
- 禁止进入导入层与控制台核心接口

## Frontend Flow

### Routes

- `/login`
  - 独立登录页
  - 用户名、密码登录

- `/change-password`
  - 首次改密页
  - 改密成功后才允许进入导入页

- `/import`
  - 仍是进入控制台前的准备页
  - 新增“已保存主机”主入口

- `/` 及控制台其他页面
  - 要求用户已登录且已完成本次导入

### Import Workspace Structure

导入页的主入口分为四个阶段：

1. `已保存主机`
2. `新建连接`
3. `硬件概览`
4. `选卡导入`

#### 已保存主机

- 普通用户只看自己的主机
- 管理员可切换“我的主机 / 全部用户主机”
- 每张主机卡片显示：
  - 标签
  - 主机地址
  - 用户名
  - 连接类型
  - 最近成功连接时间
  - owner 用户
- 操作：
  - `直接扫描`
  - `删除`

#### 新建连接

- 保留当前本机 Agent / 远程 Agent / SSH Linux 的连接录入能力
- 首次成功导入 SSH 主机后自动写入已保存主机列表

### Session State

前端新增独立 auth store，职责如下：

- 保存当前用户信息
- 保存 session token
- 应用启动时调用 `/api/auth/me` 恢复登录态
- 为 API 请求自动注入认证头

现有 app store 继续负责：

- `runtime_status`
- `import_context`
- `workspace_ready`

### Route Guards

路由守卫改为两层：

1. 未登录只能访问 `/login`
2. 已登录但 `must_change_password = true` 只能访问 `/change-password`
3. 已登录但未导入只能访问 `/import`
4. 已登录且已导入才允许进入控制台页面

## Failure Semantics

- 登录失败：明确区分用户不存在、密码错误、账号禁用
- 首次管理员未改密：明确返回强制改密错误
- 已保存主机无权限访问：返回 `403`
- 主机存在但凭据无法解密：返回显式错误，并要求重新录入凭据
- SSH 目标不可达、SSH 认证失败、GPU 不存在：沿用现有明确错误返回
- 不允许任何 silent fallback、mock success 或隐式降级

## Verification Targets

### Backend

至少覆盖以下测试：

1. 默认管理员初始化
2. 登录、登出、改密、会话恢复
3. 管理员创建用户、重置密码
4. 保存主机的 owner 权限边界
5. 加密凭据存取与主密钥错误
6. 已保存主机直接扫描与直接导入
7. 普通用户不能访问他人主机，管理员可以

### Frontend

至少覆盖以下测试：

1. 路由守卫覆盖未登录、强制改密、未导入、已导入四种状态
2. auth store 的登录态恢复
3. 导入页已保存主机 tab 展示与切换
4. 免密码扫描失败时的错误展示

### Regression

必须保证：

- 控制台仍然只显示和治理本次导入选中的卡
- 本地模式、远程 Agent、SSH Linux 三类入口继续可用
- 导入层与控制台的职责边界不回退

## Non-Goals

- 不做用户自助注册
- 不做找回密码和邮件验证
- 不做 MFA
- 不把控制台改成跨会话持久管理所有历史主机
- 不把已保存主机系统扩展成通用 CMDB

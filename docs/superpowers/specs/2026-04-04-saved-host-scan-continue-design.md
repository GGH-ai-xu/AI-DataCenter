# Saved Host Scan-Continue Flow Design

## Goal

让导入层中的“已保存主机”真正成为可复用入口：用户点击已保存主机主按钮后，系统立即使用该记录完成扫描，自动进入“硬件概览”，并在后续“选卡导入”阶段继续沿用这条已保存主机绑定关系，无需再次扫描或退化成手动连接草稿。

## Scope

本次设计只覆盖导入准备页的前端交互与测试：

- `frontend/src/composables/useImportWorkspace.js`
- `frontend/src/components/import/ImportSavedHostsStage.vue`
- `frontend/src/components/import/ImportHardwareStage.vue`
- `frontend/src/components/import/ImportSelectionStage.vue`
- 与上述行为直接相关的前端测试

本次不改：

- 后端 `/api/system/import-context/scan` 和 `/api/system/import-context` 协议
- 已保存主机数据库结构
- 控制台页的过滤与治理边界

## Current Problem

当前“已保存主机”卡片的主按钮语义是“扫描一次”，但扫描完成后缺少明确的续接状态：

1. 用户期望的是“复用这条主机，继续走后续导入流程”，而不是单次扫描动作。
2. 页面虽然支持 `saved_host_id` 扫描和提交，但前端没有把“当前仍绑定这条已保存主机”稳定表达出来。
3. 用户难以判断后续提交到底会沿用已保存主机，还是已经退回到手动连接模式。
4. 普通连接失败和凭据失效的回退语义不同，但当前界面没有把这两类分开表达成稳定流程。

## Confirmed Behavior

### Primary Interaction

- “已保存主机”主按钮仍然是扫描型动作，不新增“直接导入”按钮。
- 用户点击主按钮后，立即调用现有 `scanImportContext({ saved_host_id })`。
- 扫描成功后自动切换到 `hardware` 阶段。
- 扫描结果继续作为后续“选卡导入”的数据来源，不再要求二次扫描。

### Binding Model

- 只要用户没有显式切换到手动连接模式，`selectedSavedHostId` 必须持续保留。
- 后续导入提交继续发送 `saved_host_id`，不改写成手动 `provider + credentials`。
- 用户一旦点击“编辑连接”或主动修改连接字段，才清除这次绑定关系。

### Selection Behavior

- 扫描成功后默认选中当前扫描到的全部 GPU。
- 用户在“选卡导入”阶段可以取消部分勾选。
- 如果扫描结果没有 GPU，则允许进入“硬件概览”查看主机状态，但导入按钮保持禁用。

## Data Flow

### Saved Host Happy Path

1. 用户在 `ImportSavedHostsStage` 点击主按钮。
2. `useImportWorkspace.handleSavedHostScan(hostId)` 将 `selectedSavedHostId` 设为该主机。
3. `scanTarget()` 发送 `saved_host_id` 请求。
4. 扫描成功后：
   - 保留 `selectedSavedHostId`
   - 写入 `scanResult`
   - 根据返回 GPU 初始化 `selectedGpuIndexes`
   - 将 `activeStage` 切到 `hardware`
5. 用户浏览硬件后切到 `selection` 阶段。
6. 用户点击“导入并进入控制台”时，`payloadBase()` 继续返回 `{ saved_host_id }`。
7. `commitImportContext()` 成功后进入控制台。

### Exit From Saved Host Mode

只有以下行为会清空 `selectedSavedHostId`：

- 点击“编辑连接”
- 修改手动连接字段：
  - `providerType`
  - `agentUrl`
  - `agentLabel`
  - SSH 的 `host`
  - SSH 的 `port`
  - SSH 的 `username`
  - `authType`

这些行为意味着用户已经不再信任当前已保存主机记录，而是在构造新的连接目标。

## UI Changes

### Saved Hosts Stage

- 主按钮文案从“直接扫描”调整为“扫描并继续”。
- 卡片仍保留“编辑连接”和“删除记录”。
- 扫描失败但仍属于可重试失败时，用户停留在本阶段，直接重试即可。

### Hardware Stage

在“硬件概览”顶部新增一条紧凑的复用摘要条，明确显示：

- 当前复用主机标签
- 连接目标摘要，例如 `dell@10.151.225.108:22`
- 当前模式来自“已保存主机”

该摘要条只用于表达“后续提交仍绑定这条主机”，不提供切换入口。

### Selection Stage

“选卡导入”页沿用同一条复用摘要条，让用户在最终提交前仍然清楚：

- 当前候选 GPU 来自哪条已保存主机
- 当前提交仍会使用 `saved_host_id`

这样用户在“硬件概览”与“选卡导入”之间不会丢失上下文。

## Error Handling

### Credential Recovery Path

如果已保存主机扫描失败，且原因属于凭据不可读或缺失：

- 保持现有恢复策略
- 自动切到“连接来源”
- 带出该主机的 `host / port / username / authType`
- 清空 `selectedSavedHostId`
- 清空 `scanResult` 和已选 GPU

此时页面语义已经转成“基于旧记录快速补录凭据”，不再是复用已保存主机直连。

### Retryable Failure Path

如果扫描失败，但不是凭据问题，例如：

- SSH 连接被拒绝
- 目标离线
- 远端命令执行失败

则：

- 仍停留在“已保存主机”阶段
- 保留 `selectedSavedHostId`
- 不自动切换到“连接来源”
- 反馈错误文本，允许用户直接重试

这样可以避免把普通网络波动误判成“这条记录必须改写”。

## State Rules

### Source Of Truth

导入准备页中与已保存主机续接最相关的状态只有三类：

- `selectedSavedHostId`
- `scanResult`
- `selectedGpuIndexes`

三者关系应保持稳定：

- `selectedSavedHostId` 表示“后续提交绑定谁”
- `scanResult` 表示“当前验机结果是什么”
- `selectedGpuIndexes` 表示“控制台最终治理哪些卡”

### No Hidden Mode Switch

页面不能在用户无感知的情况下把“已保存主机模式”改成“手动连接模式”。

允许清空绑定态的操作必须是显式且可解释的：

- 编辑连接
- 改连接字段
- 凭据恢复

普通扫描失败不属于模式切换信号。

## Testing Targets

需要先补前端回归测试，再改实现。至少覆盖以下行为：

1. 点击已保存主机主按钮后，扫描成功会：
   - 保留 `selectedSavedHostId`
   - 写入 `scanResult`
   - 初始化 `selectedGpuIndexes`
   - 自动切到 `hardware`
2. 已保存主机扫描成功后，最终提交导入时发送的是 `saved_host_id`，不是手动 `provider / credentials`
3. 凭据失效时会切到“连接来源”并清空绑定态
4. 普通扫描失败不会错误清空 `selectedSavedHostId`
5. “硬件概览”和“选卡导入”都能显示复用摘要条
6. 已保存主机主按钮文案已改为“扫描并继续”

## Non-Goals

- 不在已保存主机卡片上增加“一键直接进入控制台”能力
- 不保存“上次导入的 GPU 勾选范围”到已保存主机记录
- 不让控制台承担已保存主机切换入口
- 不增加新的后端字段来表达“当前复用主机摘要”

## Implementation Notes

- 优先复用现有 `saved_host_id` 接口契约，不引入新的请求模型
- 复用摘要条应由导入准备页已有数据组合生成，不依赖后端新增聚合字段
- 相关文本应保持中文一致，避免同时出现“直接扫描”和“扫描并继续”两套语义

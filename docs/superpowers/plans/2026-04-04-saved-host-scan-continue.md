# Saved Host Scan-Continue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让导入层中的“已保存主机”在点击后自动完成扫描、进入硬件概览，并在后续选卡与提交时继续沿用 `saved_host_id`。

**Architecture:** 把 `useImportWorkspace` 中与“已保存主机续接”相关的状态流转抽到可测试的控制器里，用纯 `node:test` 锁定扫描成功、提交导入和失败回退三类行为。UI 层新增一个独立的“当前复用主机”摘要条组件，由硬件概览和选卡导入复用，避免把同一份文案和布局逻辑散落到多个大文件中。

**Tech Stack:** Vue 3 Composition API、Pinia、Vue Router、Node `node:test`、Python `unittest`。

---

## Implementation Assumptions

- 不新增后端字段，继续只使用现有的 `saved_host_id`、`scanImportContext()` 和 `commitImportContext()` 协议。
- “扫描并继续”只表示自动扫描并进入后续准备流程，不表示跳过硬件概览或直接进入控制台。
- 普通扫描失败只保留绑定态并提示重试；凭据失效才切回“连接来源”补录模式。
- 所有验证命令都在 Windows 环境执行，不使用 WSL 运行前端测试或构建。

## File Map

**Create:**
- `frontend/src/composables/createImportWorkspaceController.js`
  Purpose: 承载导入页的大部分状态、扫描/提交逻辑和 `saved_host_id` 续接行为，脱离 `onMounted()` 后可直接单测。
- `frontend/src/composables/createImportWorkspaceController.test.js`
  Purpose: 锁定“已保存主机扫描成功保留绑定态”“导入提交继续使用 `saved_host_id`”“普通失败不清空绑定态”。
- `frontend/src/components/import/ImportSavedHostSummaryBar.vue`
  Purpose: 在硬件概览和选卡导入阶段展示“当前复用主机”摘要条，避免在两个大组件里重复写同一套 UI。

**Modify:**
- `frontend/src/composables/useImportWorkspace.js`
  Purpose: 收缩为薄封装，只负责组装依赖和生命周期触发，避免继续增长到超过 300 行。
- `frontend/src/components/import/ImportSavedHostsStage.vue`
  Purpose: 把主按钮文案改成“扫描并继续”。
- `frontend/src/components/import/ImportHardwareStage.vue`
  Purpose: 接入复用摘要条，并在摘要区继续展示当前扫描结果。
- `frontend/src/components/import/ImportSelectionStage.vue`
  Purpose: 接入同一条复用摘要条，明确最终提交仍绑定已保存主机。
- `frontend/src/views/ImportWorkspace.vue`
  Purpose: 把控制器暴露的 `savedHostSummary` 传给硬件概览和选卡导入阶段。
- `frontend/src/lib/importRecovery.test.js`
  Purpose: 增加“普通失败不触发凭据恢复”的回归测试。
- `tests/test_import_layer_structure.py`
  Purpose: 锁定“扫描并继续”文案、复用摘要条组件和视图接线。

---

### Task 1: Extract A Testable Import Workspace Controller

**Files:**
- Create: `frontend/src/composables/createImportWorkspaceController.js`
- Create: `frontend/src/composables/createImportWorkspaceController.test.js`
- Modify: `frontend/src/composables/useImportWorkspace.js`
- Modify: `frontend/src/lib/importRecovery.test.js`
- Test: `frontend/src/composables/createImportWorkspaceController.test.js`
- Test: `frontend/src/lib/importRecovery.test.js`

- [ ] **Step 1: Write the failing controller tests**

Create `frontend/src/composables/createImportWorkspaceController.test.js`:

```js
import test from 'node:test'
import assert from 'node:assert/strict'
import { ref } from 'vue'

import { createImportWorkspaceController } from './createImportWorkspaceController.js'

function createSavedHostsStub(hosts = []) {
  return {
    hosts: ref(hosts),
    scope: ref('mine'),
    loading: ref(false),
    errorText: ref(''),
    deletingId: ref(null),
    loadHosts: async () => hosts,
    deleteHost: async () => ({ data: { success: true } }),
  }
}

function createStoreStub() {
  return {
    importContext: null,
    workspaceReady: false,
    setImportContext(value) {
      this.importContext = value
    },
    setWorkspaceReady(value) {
      this.workspaceReady = Boolean(value)
    },
  }
}

function createRouterStub() {
  return {
    replaced: [],
    async replace(path) {
      this.replaced.push(path)
    },
  }
}

test('saved host scan keeps binding and advances to hardware', async () => {
  const scanPayloads = []
  const controller = createImportWorkspaceController({
    router: createRouterStub(),
    store: createStoreStub(),
    auth: { currentUser: { role: 'admin' } },
    savedHosts: createSavedHostsStub([
      {
        id: 1,
        label: 'ssh',
        provider_type: 'ssh_linux',
        host: '10.151.225.108',
        port: 22,
        username: 'dell',
        auth_type: 'password',
        credential_status: 'ok',
      },
    ]),
    api: {
      getImportContext: async () => ({ data: { imported_gpu_indexes: [] } }),
      scanImportContext: async (payload) => {
        scanPayloads.push(payload)
        return {
          data: {
            success: true,
            message: '扫描成功',
            provider: {
              provider_type: 'ssh_linux',
              label: 'ssh',
              host: '10.151.225.108',
              port: 22,
              username: 'dell',
              auth_type: 'password',
            },
            gpus: [{ index: 0 }, { index: 2 }],
          },
        }
      },
      commitImportContext: async () => {
        throw new Error('not used in this test')
      },
    },
  })

  await controller.handleSavedHostScan(1)

  assert.deepEqual(scanPayloads, [{ saved_host_id: 1 }])
  assert.equal(controller.selectedSavedHostId.value, 1)
  assert.equal(controller.activeStage.value, 'hardware')
  assert.deepEqual(controller.selectedGpuIndexes.value, [0, 2])
  assert.equal(controller.savedHostSummary.value.target, 'dell@10.151.225.108:22')
})

test('saved host import continues to commit saved_host_id only', async () => {
  const commitPayloads = []
  const router = createRouterStub()
  const store = createStoreStub()
  const controller = createImportWorkspaceController({
    router,
    store,
    auth: { currentUser: { role: 'admin' } },
    savedHosts: createSavedHostsStub([
      {
        id: 1,
        label: 'ssh',
        provider_type: 'ssh_linux',
        host: '10.151.225.108',
        port: 22,
        username: 'dell',
        auth_type: 'password',
        credential_status: 'ok',
      },
    ]),
    api: {
      getImportContext: async () => ({ data: { imported_gpu_indexes: [] } }),
      scanImportContext: async () => ({
        data: {
          success: true,
          message: '扫描成功',
          provider: {
            provider_type: 'ssh_linux',
            label: 'ssh',
            host: '10.151.225.108',
            port: 22,
            username: 'dell',
            auth_type: 'password',
          },
          gpus: [{ index: 0 }, { index: 1 }],
        },
      }),
      commitImportContext: async (payload) => {
        commitPayloads.push(payload)
        return {
          data: {
            import_context: {
              valid: true,
              imported_gpu_indexes: payload.gpu_indexes,
            },
          },
        }
      },
    },
  })

  await controller.handleSavedHostScan(1)
  controller.selectedGpuIndexes.value = [1]
  await controller.handleImport()

  assert.deepEqual(commitPayloads, [{ saved_host_id: 1, gpu_indexes: [1] }])
  assert.deepEqual(store.importContext.imported_gpu_indexes, [1])
  assert.deepEqual(router.replaced, ['/'])
})

test('retryable scan failure keeps saved host binding for direct retry', async () => {
  const controller = createImportWorkspaceController({
    router: createRouterStub(),
    store: createStoreStub(),
    auth: { currentUser: { role: 'admin' } },
    savedHosts: createSavedHostsStub([
      {
        id: 1,
        label: 'ssh',
        provider_type: 'ssh_linux',
        host: '10.151.225.108',
        port: 22,
        username: 'dell',
        auth_type: 'password',
        credential_status: 'ok',
      },
    ]),
    api: {
      getImportContext: async () => ({ data: { imported_gpu_indexes: [] } }),
      scanImportContext: async () => {
        const error = new Error('ssh connect failed')
        error.response = { data: { detail: 'Permission denied for user dell on host 10.151.225.108' } }
        throw error
      },
      commitImportContext: async () => ({ data: {} }),
    },
  })

  await controller.handleSavedHostScan(1)

  assert.equal(controller.selectedSavedHostId.value, 1)
  assert.equal(controller.activeStage.value, 'saved')
  assert.match(controller.feedback.value.text, /Permission denied/)
})
```

Extend `frontend/src/lib/importRecovery.test.js` with the retryable-failure assertion:

```js
test('resolveSavedHostScanFailure keeps saved host flow for retryable runtime errors', () => {
  const result = resolveSavedHostScanFailure({
    detail: 'Permission denied for user dell on host 10.151.225.108',
    host: {
      id: 1,
      provider_type: 'ssh_linux',
      label: 'ssh',
      host: '10.151.225.108',
      port: 22,
      username: 'dell',
      auth_type: 'password',
      credential_status: 'ok',
    },
  })

  assert.equal(result.shouldRecoverSavedHost, false)
  assert.match(result.feedbackText, /Permission denied/)
})
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run from Windows PowerShell:

```powershell
cd E:\Code\AI-DataCenter\frontend
npm test -- src\composables\createImportWorkspaceController.test.js src\lib\importRecovery.test.js
```

Expected:

- The command fails because `createImportWorkspaceController.js` does not exist yet.
- That red state proves the new continuation tests are guarding code that has not been implemented.

- [ ] **Step 3: Implement the controller and thin wrapper**

Create `frontend/src/composables/createImportWorkspaceController.js`:

```js
import { computed, reactive, ref, watch } from 'vue'

import { formatImportedGpuLabel, hasValidImportContext } from '../lib/importContext.js'
import { resolveSavedHostScanFailure } from '../lib/importRecovery.js'
import {
  buildImportCredentialPayload,
  buildImportProviderPayload,
  IMPORT_STAGE_TABS,
  resolveImportAgentUrl,
  resolveImportConnectionSummary,
} from '../lib/importWorkbench.js'
import {
  applySavedHostRecovery,
  clearScanState,
  createSshForm,
  errorDetail,
  findSavedHost,
  responseTarget,
} from '../lib/importWorkspaceState.js'

const DEFAULT_SSH_PORT = 22

function savedHostTarget(host) {
  if (!host) return ''
  if (host.agent_url) return host.agent_url
  return `${host.username || 'user'}@${host.host || 'host'}:${host.port || DEFAULT_SSH_PORT}`
}

export function createImportWorkspaceController({ router, store, auth, savedHosts, api }) {
  const providerType = ref('http_local')
  const agentUrl = ref('')
  const agentLabel = ref('本机 Agent')
  const authType = ref('password')
  const hostFingerprint = ref('')
  const activeStage = ref('saved')
  const selectedSavedHostId = ref(null)
  const syncingSavedHost = ref(false)
  const sshForm = reactive(createSshForm())
  const scanBusy = ref(false)
  const importBusy = ref(false)
  const feedback = ref(null)
  const scanResult = ref(null)
  const selectedGpuIndexes = ref([])

  const currentContext = computed(() => store.importContext)
  const hasCurrentScope = computed(() => hasValidImportContext(currentContext.value))
  const canViewAllSavedHosts = computed(() => auth.currentUser?.role === 'admin')
  const importedCountLabel = computed(() => formatImportedGpuLabel(selectedGpuIndexes.value))
  const activeSavedHost = computed(() =>
    findSavedHost(savedHosts.hosts.value, selectedSavedHostId.value))
  const savedHostSummary = computed(() => {
    const host = activeSavedHost.value
    if (!host || !scanResult.value?.success) return null
    return {
      label: host.label || '已保存主机',
      target: savedHostTarget(host),
      tone: host.credential_status || 'ok',
    }
  })

  function payloadBase() {
    if (selectedSavedHostId.value) {
      return { saved_host_id: selectedSavedHostId.value }
    }
    return {
      provider: buildImportProviderPayload({
        providerType: providerType.value,
        agentLabel: agentLabel.value,
        agentUrl: agentUrl.value,
        authType: authType.value,
        hostFingerprint: hostFingerprint.value,
        sshForm,
      }),
      credentials: buildImportCredentialPayload({
        providerType: providerType.value,
        authType: authType.value,
        sshForm,
      }),
    }
  }

  function applyTarget(target) {
    syncingSavedHost.value = true
    providerType.value = target.provider_type || providerType.value
    agentLabel.value = target.label || agentLabel.value
    agentUrl.value = target.agent_url || ''
    authType.value = target.auth_type || 'password'
    hostFingerprint.value = target.host_fingerprint || ''
    sshForm.host = target.host || ''
    sshForm.port = target.port || DEFAULT_SSH_PORT
    sshForm.username = target.username || ''
    sshForm.sudoEnabled = Boolean(target.sudo_enabled)
    syncingSavedHost.value = false
  }

  function applyScanResponse(data) {
    scanResult.value = data
    applyTarget(responseTarget(data))
    hostFingerprint.value = data?.provider?.host_fingerprint || data?.capabilities?.host_fingerprint || ''
    selectedGpuIndexes.value = data.success ? data.gpus.map((gpu) => Number(gpu.index)) : []
    feedback.value = { tone: data.success ? 'ok' : 'warning', text: data.message || '扫描失败' }
    if (data.success) activeStage.value = 'hardware'
  }

  async function scanTarget(payload, host = null) {
    scanBusy.value = true
    feedback.value = null
    try {
      const { data } = await api.scanImportContext(payload)
      applyScanResponse(data)
    } catch (error) {
      clearScanState(scanResult, selectedGpuIndexes)
      const result = resolveSavedHostScanFailure({
        detail: errorDetail(error, '扫描失败'),
        host,
      })
      if (result.shouldRecoverSavedHost && host) {
        applySavedHostRecovery({
          host,
          feedbackText: result.feedbackText,
          applyTarget,
          sshForm,
          scanResult,
          selectedGpuIndexes,
          activeStage,
          feedback,
          selectedSavedHostId,
        })
      } else {
        feedback.value = { tone: 'error', text: result.feedbackText }
      }
    } finally {
      scanBusy.value = false
    }
  }

  async function handleSavedHostScan(hostId) {
    const host = findSavedHost(savedHosts.hosts.value, hostId)
    selectedSavedHostId.value = Number(hostId)
    const result = resolveSavedHostScanFailure({ host })
    if (result.shouldRecoverSavedHost && host) {
      applySavedHostRecovery({
        host,
        feedbackText: result.feedbackText,
        applyTarget,
        sshForm,
        scanResult,
        selectedGpuIndexes,
        activeStage,
        feedback,
        selectedSavedHostId,
      })
      return
    }
    await scanTarget(payloadBase(), host)
  }

  async function handleImport() {
    importBusy.value = true
    feedback.value = null
    try {
      const { data } = await api.commitImportContext({
        ...payloadBase(),
        gpu_indexes: selectedGpuIndexes.value,
      })
      store.setImportContext(data.import_context)
      store.setWorkspaceReady(true)
      await savedHosts.loadHosts(savedHosts.scope.value)
      await router.replace('/')
    } finally {
      importBusy.value = false
    }
  }

  watch([providerType, agentUrl, agentLabel, authType], () => {
    if (syncingSavedHost.value) return
    selectedSavedHostId.value = null
  })
  watch([() => sshForm.host, () => sshForm.port, () => sshForm.username], () => {
    if (syncingSavedHost.value) return
    selectedSavedHostId.value = null
  })

  return {
    activeStage,
    agentLabel,
    agentUrl,
    authType,
    canViewAllSavedHosts,
    currentAgentUrl: computed(() => resolveImportAgentUrl({
      providerType: providerType.value,
      scanResult: scanResult.value,
      agentUrl: agentUrl.value,
      sshForm,
    })),
    connectionSummary: computed(() => resolveImportConnectionSummary({
      providerType: providerType.value,
      currentAgentUrl: resolveImportAgentUrl({
        providerType: providerType.value,
        scanResult: scanResult.value,
        agentUrl: agentUrl.value,
        sshForm,
      }),
      scanBusy: scanBusy.value,
      scanResult: scanResult.value,
    })),
    canSubmitImport: computed(() => Boolean(scanResult.value?.success) && selectedGpuIndexes.value.length > 0),
    feedback,
    heroTitle: computed(() => (hasCurrentScope.value ? '重新导入管理范围' : '进入控制台前的准备')),
    hostFingerprint,
    importBusy,
    providerType,
    savedHostDeleteBusyId: savedHosts.deletingId,
    savedHostErrorText: savedHosts.errorText,
    savedHostList: savedHosts.hosts,
    savedHostLoading: savedHosts.loading,
    savedHostScope: savedHosts.scope,
    savedHostSummary,
    scanBusy,
    scanResult,
    selectedGpuIndexes,
    selectedSavedHostId,
    sshForm,
    tabs: IMPORT_STAGE_TABS,
    handleImport,
    handleSavedHostScan,
    refreshContext: async () => {
      const { data } = await api.getImportContext()
      store.setImportContext(data)
      selectedGpuIndexes.value = (data?.imported_gpu_indexes || []).map((value) => Number(value))
    },
    refreshSavedHosts: async (scope = savedHosts.scope.value) => savedHosts.loadHosts(scope),
  }
}
```

Shrink `frontend/src/composables/useImportWorkspace.js` to a thin wrapper:

```js
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

import { commitImportContext, getImportContext, scanImportContext } from '../services/api.js'
import { useAppStore } from '../stores/app.js'
import { useAuthStore } from '../stores/auth.js'
import { createImportWorkspaceController } from './createImportWorkspaceController.js'
import { useSavedHosts } from './useSavedHosts.js'

export function useImportWorkspace() {
  const controller = createImportWorkspaceController({
    router: useRouter(),
    store: useAppStore(),
    auth: useAuthStore(),
    savedHosts: useSavedHosts(),
    api: {
      getImportContext,
      scanImportContext,
      commitImportContext,
    },
  })

  onMounted(() => {
    void controller.refreshContext().catch(() => {})
    void controller.refreshSavedHosts().catch(() => {})
  })

  return controller
}
```

- [ ] **Step 4: Run the focused tests to verify they pass**

Run from Windows PowerShell:

```powershell
cd E:\Code\AI-DataCenter\frontend
npm test -- src\composables\createImportWorkspaceController.test.js src\lib\importRecovery.test.js
```

Expected:

- `3` controller tests pass.
- `importRecovery.test.js` still passes with the new retryable-failure assertion.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/composables/createImportWorkspaceController.js frontend/src/composables/createImportWorkspaceController.test.js frontend/src/composables/useImportWorkspace.js frontend/src/lib/importRecovery.test.js
git commit -m "feat: retain saved host binding through import flow"
```

---

### Task 2: Wire The Saved Host Continuation UI

**Files:**
- Create: `frontend/src/components/import/ImportSavedHostSummaryBar.vue`
- Modify: `frontend/src/components/import/ImportSavedHostsStage.vue`
- Modify: `frontend/src/components/import/ImportHardwareStage.vue`
- Modify: `frontend/src/components/import/ImportSelectionStage.vue`
- Modify: `frontend/src/views/ImportWorkspace.vue`
- Modify: `tests/test_import_layer_structure.py`
- Test: `tests/test_import_layer_structure.py`

- [ ] **Step 1: Write the failing structure assertions**

Update `tests/test_import_layer_structure.py` with a new test:

```python
    def test_saved_host_scan_continue_ui_is_wired_through_hardware_and_selection(self):
        saved_stage = (ROOT / "frontend/src/components/import/ImportSavedHostsStage.vue").read_text(encoding="utf-8")
        hardware_stage = (ROOT / "frontend/src/components/import/ImportHardwareStage.vue").read_text(encoding="utf-8")
        selection_stage = (ROOT / "frontend/src/components/import/ImportSelectionStage.vue").read_text(encoding="utf-8")
        workspace_view = (ROOT / "frontend/src/views/ImportWorkspace.vue").read_text(encoding="utf-8")
        summary_bar = (ROOT / "frontend/src/components/import/ImportSavedHostSummaryBar.vue")

        self.assertTrue(summary_bar.exists())
        self.assertIn("扫描并继续", saved_stage)
        self.assertIn("ImportSavedHostSummaryBar", hardware_stage)
        self.assertIn("ImportSavedHostSummaryBar", selection_stage)
        self.assertIn(':saved-host-summary="workspace.savedHostSummary"', workspace_view)
        self.assertIn("当前复用主机", summary_bar.read_text(encoding="utf-8"))
```

- [ ] **Step 2: Run the structure test to verify it fails**

Run from Windows PowerShell in repository root:

```powershell
cd E:\Code\AI-DataCenter
python -m unittest tests.test_import_layer_structure -v
```

Expected:

- Fail because `ImportSavedHostSummaryBar.vue` does not exist yet.
- Fail because “扫描并继续” and `savedHostSummary` wiring are not present yet.

- [ ] **Step 3: Implement the summary bar and stage wiring**

Create `frontend/src/components/import/ImportSavedHostSummaryBar.vue`:

```vue
<script setup>
const props = defineProps({
  savedHostSummary: {
    type: Object,
    default: null,
  },
})
</script>

<template>
  <section v-if="props.savedHostSummary" class="import-saved-host-summary">
    <span class="import-saved-host-summary__label">当前复用主机</span>
    <strong class="import-saved-host-summary__title">
      {{ props.savedHostSummary.label }}
    </strong>
    <span class="import-saved-host-summary__target">
      {{ props.savedHostSummary.target }}
    </span>
  </section>
</template>

<style scoped>
.import-saved-host-summary {
  display: grid;
  gap: 6px;
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid rgba(58, 95, 75, 0.12);
  background: rgba(244, 250, 247, 0.88);
}

.import-saved-host-summary__label {
  font-size: 0.74rem;
  letter-spacing: 0.08em;
  color: var(--text-muted);
}

.import-saved-host-summary__title,
.import-saved-host-summary__target {
  line-height: 1.6;
  word-break: break-word;
}
</style>
```

Modify `frontend/src/components/import/ImportSavedHostsStage.vue`:

```vue
function scanActionLabel(host) {
  return host.credential_status === 'unreadable' ? '补录凭据' : '扫描并继续'
}
```

Modify `frontend/src/components/import/ImportHardwareStage.vue`:

```vue
<script setup>
import { computed, ref } from 'vue'
import ImportHardwareSummary from './ImportHardwareSummary.vue'
import ImportSavedHostSummaryBar from './ImportSavedHostSummaryBar.vue'

const props = defineProps({
  savedHostSummary: { type: Object, default: null },
  providerType: { type: String, required: true },
  agentLabel: { type: String, default: '' },
  agentUrl: { type: String, default: '' },
  agentHealth: { type: Object, default: null },
  system: { type: Object, default: null },
  capabilities: { type: Object, default: null },
  gpus: { type: Array, default: () => [] },
})
</script>

<template>
  <section class="import-hardware-stage">
    <div class="import-hardware-stage__main">
      <ImportSavedHostSummaryBar :saved-host-summary="props.savedHostSummary" />
      <ImportHardwareSummary
        :provider-type="props.providerType"
        :agent-label="props.agentLabel"
        :agent-url="props.agentUrl"
        :agent-health="props.agentHealth"
        :system="props.system"
        :capabilities="props.capabilities"
      />
    </div>
  </section>
</template>
```

Modify `frontend/src/components/import/ImportSelectionStage.vue`:

```vue
<script setup>
import { computed, ref } from 'vue'
import ImportSavedHostSummaryBar from './ImportSavedHostSummaryBar.vue'
import ImportGpuGrid from './ImportGpuGrid.vue'

const props = defineProps({
  savedHostSummary: { type: Object, default: null },
  gpus: { type: Array, default: () => [] },
  modelValue: { type: Array, default: () => [] },
})
</script>

<template>
  <section class="import-selection-stage">
    <div class="import-selection-stage__main">
      <ImportSavedHostSummaryBar :saved-host-summary="props.savedHostSummary" />
      <section class="tech-card import-selection-stage__toolbar-card">
        <div class="import-selection-stage__toolbar-head">
          <div>
            <div class="section-title">选卡导入</div>
            <p class="import-selection-stage__copy">
              控制台后续只显示和治理这里勾选的卡。切换视图不会改变实际已选范围。
            </p>
          </div>
        </div>
      </section>
    </div>
  </section>
</template>
```

Modify `frontend/src/views/ImportWorkspace.vue`:

```vue
      <ImportHardwareStage
        v-else-if="workspace.activeStage === 'hardware'"
        :saved-host-summary="workspace.savedHostSummary"
        :provider-type="workspace.providerType"
        :agent-label="workspace.scanResult?.agent_label || workspace.agentLabel"
        :agent-url="workspace.currentAgentUrl"
        :agent-health="workspace.scanResult?.agent_health || null"
        :system="workspace.scanResult?.system || null"
        :capabilities="workspace.scanResult?.capabilities || null"
        :gpus="workspace.scanResult?.gpus || []"
      />
      <ImportSelectionStage
        v-else
        :saved-host-summary="workspace.savedHostSummary"
        :model-value="workspace.selectedGpuIndexes"
        :gpus="workspace.scanResult?.gpus || []"
        @update:model-value="workspace.selectedGpuIndexes = $event"
      />
```

- [ ] **Step 4: Run the structure test again**

Run from Windows PowerShell:

```powershell
cd E:\Code\AI-DataCenter
python -m unittest tests.test_import_layer_structure -v
```

Expected:

- `tests.test_import_layer_structure` passes.
- New assertions confirm the summary component exists and is wired through both later stages.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/import/ImportSavedHostSummaryBar.vue frontend/src/components/import/ImportSavedHostsStage.vue frontend/src/components/import/ImportHardwareStage.vue frontend/src/components/import/ImportSelectionStage.vue frontend/src/views/ImportWorkspace.vue tests/test_import_layer_structure.py
git commit -m "feat: continue saved host scans through import stages"
```

---

## Final Verification

Run all relevant checks from Windows PowerShell after both tasks:

```powershell
cd E:\Code\AI-DataCenter\frontend
npm test
npm run build

cd E:\Code\AI-DataCenter
python -m unittest tests.test_import_layer_structure -v
```

Expected:

- `npm test` passes with the new controller regression coverage.
- `npm run build` succeeds.
- `tests.test_import_layer_structure` passes with the new summary-bar assertions.

## Spec Coverage Check

- 自动扫描并进入硬件概览: Task 1 controller tests + controller implementation.
- 保留 `selectedSavedHostId` 并在提交时继续发送 `saved_host_id`: Task 1 controller tests + payload implementation.
- 凭据失效与普通失败分流: Task 1 recovery regression + controller catch logic.
- “扫描并继续”文案与“当前复用主机”摘要条: Task 2 stage UI and structure tests.
- 不改后端协议、不改控制台边界: File map and task scopes remain strictly frontend-only.

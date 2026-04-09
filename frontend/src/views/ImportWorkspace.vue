<script setup>
import { proxyRefs } from 'vue'
import ImportConnectionStage from '../components/import/ImportConnectionStage.vue'
import ImportHardwareStage from '../components/import/ImportHardwareStage.vue'
import ImportPrepSidebar from '../components/import/ImportPrepSidebar.vue'
import ImportPrepWorkbench from '../components/import/ImportPrepWorkbench.vue'
import ImportSavedHostsStage from '../components/import/ImportSavedHostsStage.vue'
import ImportSelectionStage from '../components/import/ImportSelectionStage.vue'
import { useImportWorkspace } from '../composables/useImportWorkspace.js'


const workspace = proxyRefs(useImportWorkspace())
</script>

<template>
  <div class="import-prep-layout">
    <ImportPrepSidebar
      :title="workspace.heroTitle"
      :description="workspace.heroDescription"
      :steps="workspace.stepItems"
      :note="'控制台只治理本次导入选中的卡。你可以先复用已保存主机，再决定是否切换到手动连接。'"
    />
    <ImportPrepWorkbench
      :active-tab="workspace.activeStage"
      :tabs="workspace.tabs"
      :footer-message="workspace.footerMessage"
      :import-busy="workspace.importBusy"
      :import-disabled="!workspace.canSubmitImport"
      @update:active-tab="workspace.activeStage = $event"
      @submit="workspace.handleImport"
    >
      <ImportSavedHostsStage
        v-if="workspace.activeStage === 'saved'"
        :hosts="workspace.savedHostList"
        :loading="workspace.savedHostLoading"
        :error-text="workspace.savedHostErrorText"
        :scope="workspace.savedHostScope"
        :can-view-all="workspace.canViewAllSavedHosts"
        :active-host-id="workspace.selectedSavedHostId"
        :deleting-host-id="workspace.savedHostDeleteBusyId"
        @update:scope="workspace.refreshSavedHosts($event)"
        @refresh="workspace.refreshSavedHosts()"
        @edit="workspace.handleSavedHostEdit"
        @scan="workspace.handleSavedHostScan"
        @delete="workspace.handleDeleteSavedHost"
      />
      <ImportConnectionStage
        v-else-if="workspace.activeStage === 'source'"
        :provider-type="workspace.providerType"
        :agent-url="workspace.agentUrl"
        :agent-label="workspace.agentLabel"
        :host="workspace.sshForm.host"
        :port="workspace.sshForm.port"
        :username="workspace.sshForm.username"
        :auth-type="workspace.authType"
        :password="workspace.sshForm.password"
        :private-key="workspace.sshForm.privateKey"
        :private-key-passphrase="workspace.sshForm.privateKeyPassphrase"
        :sudo-enabled="workspace.sshForm.sudoEnabled"
        :sudo-password="workspace.sshForm.sudoPassword"
        :scan-busy="workspace.scanBusy"
        :feedback="workspace.feedback"
        :host-fingerprint="workspace.hostFingerprint"
        @update:provider-type="workspace.providerType = $event"
        @update:agent-url="workspace.agentUrl = $event"
        @update:agent-label="workspace.agentLabel = $event"
        @update:host="workspace.sshForm.host = $event"
        @update:port="workspace.sshForm.port = $event"
        @update:username="workspace.sshForm.username = $event"
        @update:auth-type="workspace.authType = $event"
        @update:password="workspace.sshForm.password = $event"
        @update:private-key="workspace.sshForm.privateKey = $event"
        @update:private-key-passphrase="workspace.sshForm.privateKeyPassphrase = $event"
        @update:sudo-enabled="workspace.sshForm.sudoEnabled = $event"
        @update:sudo-password="workspace.sshForm.sudoPassword = $event"
        @scan="workspace.handleScan"
      />
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
    </ImportPrepWorkbench>
  </div>
</template>

<style scoped>
.import-prep-layout {
  position: relative;
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(320px, 390px) minmax(0, 1fr);
  gap: 24px;
  align-items: start;
  padding: 28px clamp(20px, 4vw, 48px);
  isolation: isolate;
  --import-page-bg: var(--bg-base);
  --import-panel-bg: var(--bg-card);
  --import-panel-bg-hover: var(--bg-card-hover);
  --import-surface-bg: var(--bg-primary);
  --import-surface-alt: var(--bg-secondary);
  --import-surface-soft: var(--bg-surface);
  --import-border: var(--border-color);
  --import-border-strong: var(--border-strong);
  --import-text: var(--text-primary);
  --import-text-secondary: var(--text-secondary);
  --import-text-muted: var(--text-muted);
  --import-accent: var(--accent-primary);
  --import-accent-bright: var(--accent-secondary);
  --import-accent-soft: var(--state-ok-bg);
  --import-warning: var(--accent-warning);
  --import-warning-soft: var(--state-warning-bg);
  --import-danger: var(--accent-danger);
  --import-danger-soft: var(--state-critical-bg);
}

.import-prep-layout::before {
  content: '';
  position: absolute;
  inset: 10px 10px 14px;
  border-radius: 28px;
  background: linear-gradient(180deg, var(--bg-strong), var(--import-page-bg));
  border: 1px solid var(--import-border);
  box-shadow: 0 28px 80px rgba(0, 0, 0, 0.34);
  z-index: -1;
}

.import-prep-layout :deep(.tech-card) {
  background: var(--import-panel-bg);
  border-color: var(--import-border);
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.28);
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
}

.import-prep-layout :deep(.tech-card::before),
.import-prep-layout :deep(.tech-card::after) {
  display: none;
}

.import-prep-layout :deep(.tech-card:hover) {
  transform: translateY(-2px);
  background: var(--import-panel-bg-hover);
  border-color: var(--border-hover);
  box-shadow: 0 24px 56px rgba(0, 0, 0, 0.32);
}

.import-prep-layout :deep(.section-title) {
  font-family: var(--font-ui);
  font-size: 0.74rem;
  font-weight: 600;
  letter-spacing: 0.12em;
  color: var(--import-text-muted);
}

.import-prep-layout :deep(.section-title::before) {
  width: 6px;
  height: 6px;
  background: var(--import-accent);
  box-shadow: none;
}

.import-prep-layout :deep(.status-badge) {
  min-height: 28px;
  padding: 5px 10px;
  border-radius: 999px;
  border: 1px solid var(--import-border);
  background: var(--import-surface-soft);
  box-shadow: none;
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: none;
}

.import-prep-layout :deep(.status-badge--ok) {
  color: var(--state-ok-text);
  border-color: var(--state-ok-border);
  background: var(--state-ok-bg);
}

.import-prep-layout :deep(.status-badge--warning) {
  color: var(--state-warning-text);
  border-color: var(--state-warning-border);
  background: var(--state-warning-bg);
}

.import-prep-layout :deep(.status-badge--critical) {
  color: var(--state-critical-text);
  border-color: var(--state-critical-border);
  background: var(--state-critical-bg);
}

.import-prep-layout :deep(.btn-tech) {
  min-height: 42px;
  border-radius: 12px;
  border: 1px solid var(--import-border);
  background: var(--import-surface-alt);
  color: var(--import-text);
  box-shadow: none;
}

.import-prep-layout :deep(.btn-tech:hover:not(:disabled)) {
  transform: translateY(-1px);
  border-color: var(--border-hover);
  background: var(--import-panel-bg-hover);
  box-shadow: none;
}

.import-prep-layout :deep(.btn-tech--primary) {
  border-color: transparent;
  background: var(--import-accent);
  color: #fff;
  box-shadow:
    0 10px 24px rgba(94, 106, 210, 0.22),
    inset 0 1px 0 rgba(255, 255, 255, 0.18);
}

.import-prep-layout :deep(.btn-tech--primary:hover:not(:disabled)) {
  background: var(--import-accent-bright);
}

.import-prep-layout :deep(input:not([type='checkbox']):not([type='radio'])),
.import-prep-layout :deep(textarea),
.import-prep-layout :deep(select) {
  min-height: 46px;
  border-radius: 12px;
  border: 1px solid var(--import-border);
  background: var(--import-surface-bg);
  color: var(--import-text);
  box-shadow: none;
}

.import-prep-layout :deep(input:not([type='checkbox']):not([type='radio']):focus),
.import-prep-layout :deep(textarea:focus),
.import-prep-layout :deep(select:focus) {
  border-color: var(--import-border-strong);
  box-shadow: 0 0 0 3px var(--field-focus-ring);
}

@media (max-width: 1080px) {
  .import-prep-layout {
    grid-template-columns: 1fr;
    padding: 18px 14px 26px;
  }

  .import-prep-layout::before {
    inset: 8px;
    border-radius: 22px;
  }
}
</style>

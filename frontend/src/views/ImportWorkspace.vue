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
      :connection-summary="workspace.connectionSummary"
      :selected-summary="workspace.sidebarSelectedSummary"
      :scope-summary="workspace.sidebarScopeSummary"
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
        :connection-summary="workspace.connectionSummary"
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
        :model-value="workspace.selectedGpuIndexes"
        :gpus="workspace.scanResult?.gpus || []"
        @update:model-value="workspace.selectedGpuIndexes = $event"
      />
    </ImportPrepWorkbench>
  </div>
</template>

<style scoped>
.import-prep-layout {
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(300px, 360px) minmax(0, 1fr);
  gap: 28px;
  align-items: stretch;
  padding: 32px clamp(18px, 4vw, 54px);
}

@media (max-width: 1080px) {
  .import-prep-layout {
    grid-template-columns: 1fr;
    padding: 22px 16px 28px;
  }
}
</style>

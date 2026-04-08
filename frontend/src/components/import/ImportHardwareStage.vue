<script setup>
import { computed, ref } from 'vue'
import { isImportableGpu } from '../../lib/importGpuAvailability.js'
import ImportHardwareGpuCards from './ImportHardwareGpuCards.vue'
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

const activeView = ref('cards')
const availableGpus = computed(() => props.gpus.filter((gpu) => isImportableGpu(gpu)))
const unavailableCount = computed(() => Math.max(props.gpus.length - availableGpus.value.length, 0))
const busyCount = computed(() =>
  availableGpus.value.filter((gpu) => Number(gpu.gpu_utilization || 0) > 0).length)
const idleCount = computed(() => Math.max(availableGpus.value.length - busyCount.value, 0))
const totalMemory = computed(() =>
  availableGpus.value.reduce((sum, gpu) => sum + Number(gpu.memory_total || 0), 0))
const totalMemoryUsed = computed(() =>
  availableGpus.value.reduce((sum, gpu) => sum + Number(gpu.memory_used || 0), 0))

function formatMemoryMb(value) {
  const total = Number(value || 0)
  if (!total) return '0 GB'
  return `${(total / 1024).toFixed(1)} GB`
}
</script>

<template>
  <section class="import-hardware-stage">
    <div class="import-hardware-stage__shell">
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

        <section class="tech-card import-hardware-stage__gpu-panel">
          <div class="import-hardware-stage__panel-head">
            <div>
              <div class="section-title">GPU 总览</div>
              <p class="import-hardware-stage__panel-copy">
                坏卡会保留在结果里并标成不可用，可用卡仍然可以进入下一步选卡导入。
              </p>
            </div>
            <div class="import-hardware-stage__view-toggle">
              <button
                type="button"
                class="import-hardware-stage__view-button"
                :class="{ 'import-hardware-stage__view-button--active': activeView === 'cards' }"
                @click="activeView = 'cards'"
              >
                卡片视图
              </button>
              <button
                type="button"
                class="import-hardware-stage__view-button"
                :class="{ 'import-hardware-stage__view-button--active': activeView === 'summary' }"
                @click="activeView = 'summary'"
              >
                摘要视图
              </button>
            </div>
          </div>

          <div v-if="!props.gpus.length" class="import-hardware-stage__empty">
            先在“连接来源”阶段完成一次扫描，系统才会展示 CPU 和 GPU 的真实硬件概览。
          </div>

          <ImportHardwareGpuCards v-else-if="activeView === 'cards'" :gpus="props.gpus" />

          <div v-else class="import-hardware-stage__summary-grid">
            <article class="import-hardware-stage__summary-card">
              <span>发现 GPU</span>
              <strong>{{ props.gpus.length }} 张</strong>
            </article>
            <article class="import-hardware-stage__summary-card">
              <span>可用 GPU</span>
              <strong>{{ availableGpus.length }} 张</strong>
            </article>
            <article class="import-hardware-stage__summary-card">
              <span>异常 GPU</span>
              <strong>{{ unavailableCount }} 张</strong>
            </article>
            <article class="import-hardware-stage__summary-card">
              <span>繁忙 GPU</span>
              <strong>{{ busyCount }} 张</strong>
            </article>
            <article class="import-hardware-stage__summary-card">
              <span>空闲 GPU</span>
              <strong>{{ idleCount }} 张</strong>
            </article>
            <article class="import-hardware-stage__summary-card">
              <span>总显存</span>
              <strong>{{ formatMemoryMb(totalMemoryUsed) }} / {{ formatMemoryMb(totalMemory) }}</strong>
            </article>
          </div>
        </section>
      </div>

      <aside class="tech-card import-hardware-stage__aside">
        <div class="section-title">验机摘要</div>
        <div class="import-hardware-stage__facts">
          <article class="import-hardware-stage__fact">
            <span>扫描来源</span>
            <strong>{{ props.providerType === 'ssh_linux' ? 'SSH Linux' : (props.providerType === 'http_remote' ? '远程 Agent' : '本机 Agent') }}</strong>
          </article>
          <article class="import-hardware-stage__fact">
            <span>目标地址</span>
            <strong>{{ props.agentUrl || '目标地址待识别' }}</strong>
          </article>
          <article class="import-hardware-stage__fact">
            <span>可导入范围</span>
            <strong>{{ availableGpus.length }} 张可用，{{ unavailableCount }} 张异常</strong>
          </article>
          <article class="import-hardware-stage__fact">
            <span>最近结果</span>
            <strong>{{ props.agentHealth?.status || '等待扫描' }}</strong>
          </article>
          <article v-if="props.capabilities?.host_fingerprint" class="import-hardware-stage__fact">
            <span>主机指纹</span>
            <strong>{{ props.capabilities.host_fingerprint }}</strong>
          </article>
        </div>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.import-hardware-stage,
.import-hardware-stage__main {
  display: grid;
  gap: 16px;
  min-height: 0;
}

.import-hardware-stage__shell {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(240px, 0.8fr);
  gap: 16px;
}

.import-hardware-stage__gpu-panel,
.import-hardware-stage__aside {
  display: grid;
  gap: 16px;
  padding: 20px;
}

.import-hardware-stage__panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
}

.import-hardware-stage__panel-copy,
.import-hardware-stage__fact span,
.import-hardware-stage__empty {
  font-size: 0.78rem;
  line-height: 1.7;
  color: var(--text-muted);
}

.import-hardware-stage__view-toggle {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.import-hardware-stage__view-button {
  min-height: 40px;
  padding: 0 14px;
  border-radius: 999px;
  border: 1px solid rgba(58, 95, 75, 0.12);
  background: rgba(255, 255, 255, 0.82);
  color: var(--text-secondary);
}

.import-hardware-stage__view-button--active {
  border-color: rgba(46, 139, 87, 0.18);
  background: rgba(244, 250, 247, 0.88);
  color: var(--text-primary);
}

.import-hardware-stage__summary-grid,
.import-hardware-stage__facts {
  display: grid;
  gap: 12px;
}

.import-hardware-stage__summary-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.import-hardware-stage__summary-card,
.import-hardware-stage__fact {
  display: grid;
  gap: 8px;
  padding: 16px;
  border-radius: 20px;
  background: rgba(255, 252, 247, 0.72);
  border: 1px solid rgba(26, 26, 26, 0.05);
}

.import-hardware-stage__summary-card strong,
.import-hardware-stage__fact strong {
  font-size: 0.94rem;
  line-height: 1.55;
  color: var(--text-primary);
  word-break: break-word;
}

@media (max-width: 960px) {
  .import-hardware-stage__shell,
  .import-hardware-stage__summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>

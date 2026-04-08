<script setup>
import { computed, ref } from 'vue'
import { isImportableGpu } from '../../lib/importGpuAvailability.js'
import ImportHardwareSummary from './ImportHardwareSummary.vue'
import ImportSavedHostSummaryBar from './ImportSavedHostSummaryBar.vue'
import { formatGpuMemoryBytes } from '../../lib/importHardwareFormatting.js'

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

          <div v-else-if="activeView === 'cards'" class="import-hardware-stage__cards">
            <article
              v-for="gpu in props.gpus"
              :key="gpu.index"
              class="import-hardware-stage__card"
              :class="{ 'import-hardware-stage__card--disabled': !isImportableGpu(gpu) }"
            >
              <div class="import-hardware-stage__card-head">
                <div>
                  <div class="import-hardware-stage__badge">GPU {{ gpu.index }}</div>
                  <strong>{{ gpu.name }}</strong>
                </div>
                <span
                  class="status-badge"
                  :class="!isImportableGpu(gpu)
                    ? 'status-badge--critical'
                    : Number(gpu.gpu_utilization || 0) > 0
                      ? 'status-badge--ok'
                      : 'status-badge--warning'"
                >
                  {{ !isImportableGpu(gpu) ? '不可用' : (Number(gpu.gpu_utilization || 0) > 0 ? '运行中' : '空闲') }}
                </span>
              </div>

              <div class="import-hardware-stage__metrics">
                <div>
                  <span>温度</span>
                  <strong>{{ Number(gpu.temperature || 0) }}°C</strong>
                </div>
                <div>
                  <span>功耗</span>
                  <strong>{{ Number(gpu.power_usage || 0).toFixed(0) }}W</strong>
                </div>
                <div>
                  <span>利用率</span>
                  <strong>{{ Number(gpu.gpu_utilization || 0) }}%</strong>
                </div>
                <div>
                  <span>显存</span>
                  <strong>{{ formatGpuMemoryBytes(gpu.memory_used) }} / {{ formatGpuMemoryBytes(gpu.memory_total) }}</strong>
                </div>
              </div>

              <p v-if="gpu.error" class="import-hardware-stage__error">{{ gpu.error }}</p>
            </article>
          </div>

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
              <strong>{{ formatGpuMemoryBytes(totalMemoryUsed) }} / {{ formatGpuMemoryBytes(totalMemory) }}</strong>
            </article>
          </div>
        </section>
      </div>

      <aside class="tech-card import-hardware-stage__aside">
        <div class="section-title">验机摘要</div>
        <div class="import-hardware-stage__facts">
          <article class="import-hardware-stage__fact">
            <span>扫描来源</span>
            <strong>{{ props.providerType === 'ssh_linux' ? 'SSH Linux' : (props.providerType === 'http_remote' ? '远程 Agent' : '本机') }}</strong>
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
  align-items: start;
  min-height: 0;
}

.import-hardware-stage__gpu-panel,
.import-hardware-stage__aside {
  display: grid;
  gap: 16px;
  padding: 20px;
  align-content: start;
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
  border-radius: 12px;
  border: 1px solid var(--import-border, var(--border-color));
  background: var(--import-surface-alt, rgba(255, 255, 255, 0.04));
  color: var(--import-text-secondary, var(--text-secondary));
}

.import-hardware-stage__view-button--active {
  border-color: var(--import-border-strong, rgba(94, 106, 210, 0.32));
  background: var(--import-accent-soft, rgba(94, 106, 210, 0.14));
  color: var(--import-text, var(--text-primary));
}

.import-hardware-stage__cards {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.import-hardware-stage__card {
  display: grid;
  gap: 16px;
  padding: 18px;
  border-radius: 22px;
  border: 1px solid var(--import-border, var(--border-color));
  background: var(--import-surface-soft, rgba(255, 255, 255, 0.03));
  text-align: left;
  transition: border-color 0.24s ease, background 0.24s ease, transform 0.24s ease, box-shadow 0.24s ease;
}

.import-hardware-stage__card:hover {
  transform: translateY(-1px);
  border-color: rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.05);
  box-shadow: none;
}

.import-hardware-stage__card--disabled {
  border-color: rgba(255, 120, 148, 0.22);
  background: rgba(255, 120, 148, 0.08);
  box-shadow: none;
}

.import-hardware-stage__card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.import-hardware-stage__badge {
  font-size: 0.74rem;
  color: var(--import-accent, var(--accent-primary));
  margin-bottom: 6px;
}

.import-hardware-stage__metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.import-hardware-stage__metrics div {
  display: grid;
  gap: 5px;
}

.import-hardware-stage__metrics span {
  font-size: 0.78rem;
  line-height: 1.7;
  color: var(--text-muted);
}

.import-hardware-stage__card strong,
.import-hardware-stage__metrics strong {
  font-size: 0.94rem;
  line-height: 1.55;
  color: var(--text-primary);
  word-break: break-word;
}

.import-hardware-stage__error {
  margin: 0;
  font-size: 0.78rem;
  line-height: 1.7;
  color: #ffd2de;
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
  background: var(--import-surface-soft, rgba(255, 255, 255, 0.03));
  border: 1px solid var(--import-border, var(--border-color));
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
  .import-hardware-stage__summary-grid,
  .import-hardware-stage__cards,
  .import-hardware-stage__metrics {
    grid-template-columns: 1fr;
  }
}
</style>

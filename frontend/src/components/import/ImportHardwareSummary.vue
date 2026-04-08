<script setup>
import { computed } from 'vue'
import { formatSystemMemoryBytes } from '../../lib/importHardwareFormatting.js'

const props = defineProps({
  providerType: { type: String, required: true },
  agentLabel: { type: String, default: '' },
  agentUrl: { type: String, default: '' },
  agentHealth: { type: Object, default: null },
  system: { type: Object, default: null },
  capabilities: { type: Object, default: null },
})

const facts = computed(() => [
  { label: '导入模式', value: props.providerType === 'ssh_linux' ? 'SSH Linux' : (props.providerType === 'http_remote' ? '远程 Agent' : '本机') },
  { label: '目标标签', value: props.agentLabel || (props.providerType === 'http_remote' ? '远程 Agent' : '本机') },
  { label: 'CPU 占用', value: `${Number(props.system?.cpu_percent || 0).toFixed(1)}%` },
  { label: 'CPU 线程', value: `${Number(props.system?.cpu_count || 0) || '未知'}` },
  { label: '内存总量', value: formatSystemMemoryBytes(props.system?.memory_total) },
  { label: '运行时状态', value: props.agentHealth?.status || '未连通' },
  { label: 'sudo', value: props.providerType === 'ssh_linux' ? (props.capabilities?.sudo_ready ? '可用' : '未启用') : '不适用' },
])
</script>

<template>
  <section class="tech-card import-hardware-summary">
    <div class="import-hardware-summary__head">
      <div class="section-title">扫描摘要</div>
      <span class="status-badge" :class="props.agentHealth ? 'status-badge--ok' : 'status-badge--warning'">
        {{ props.agentHealth ? '目标在线' : '等待扫描' }}
      </span>
    </div>

    <div class="import-hardware-summary__facts">
      <div v-for="fact in facts" :key="fact.label" class="import-hardware-summary__fact">
        <span>{{ fact.label }}</span>
        <strong>{{ fact.value }}</strong>
      </div>
    </div>

    <div v-if="props.agentUrl" class="import-hardware-summary__address">
      {{ props.agentUrl }}
    </div>

    <div v-if="props.capabilities?.host_fingerprint" class="import-hardware-summary__address">
      指纹：{{ props.capabilities.host_fingerprint }}
    </div>
  </section>
</template>

<style scoped>
.import-hardware-summary {
  display: grid;
  gap: 16px;
  padding: 20px;
}

.import-hardware-summary__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.import-hardware-summary__facts {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.import-hardware-summary__fact {
  display: grid;
  gap: 6px;
  padding: 14px;
  border-radius: 16px;
  background: var(--import-surface-soft, rgba(255, 255, 255, 0.03));
  border: 1px solid var(--import-border, var(--border-color));
}

.import-hardware-summary__fact span,
.import-hardware-summary__address {
  font-size: 0.76rem;
  line-height: 1.7;
  color: var(--import-text-muted, var(--text-muted));
  word-break: break-word;
}

.import-hardware-summary__fact strong {
  font-size: 1rem;
  color: var(--import-text, var(--text-primary));
}

@media (max-width: 900px) {
  .import-hardware-summary__facts {
    grid-template-columns: 1fr;
  }
}
</style>

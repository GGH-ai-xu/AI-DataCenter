<script setup>
import { isImportableGpu } from '../../lib/importGpuAvailability.js'

const props = defineProps({
  gpus: { type: Array, default: () => [] },
})

function formatMemoryMb(value) {
  const total = Number(value || 0)
  if (!total) return '0 GB'
  return `${(total / 1024).toFixed(1)} GB`
}

function gpuBadgeClass(gpu) {
  if (!isImportableGpu(gpu)) return 'status-badge--critical'
  return Number(gpu.gpu_utilization || 0) > 0 ? 'status-badge--ok' : 'status-badge--warning'
}

function gpuBadgeText(gpu) {
  if (!isImportableGpu(gpu)) return '不可用'
  return Number(gpu.gpu_utilization || 0) > 0 ? '运行中' : '空闲'
}
</script>

<template>
  <div class="import-hardware-gpu-cards">
    <article
      v-for="gpu in props.gpus"
      :key="gpu.index"
      class="import-hardware-gpu-cards__card"
      :class="{ 'import-hardware-gpu-cards__card--disabled': !isImportableGpu(gpu) }"
    >
      <div class="import-hardware-gpu-cards__head">
        <div>
          <div class="import-hardware-gpu-cards__badge">GPU {{ gpu.index }}</div>
          <strong>{{ gpu.name }}</strong>
        </div>
        <span class="status-badge" :class="gpuBadgeClass(gpu)">
          {{ gpuBadgeText(gpu) }}
        </span>
      </div>

      <div class="import-hardware-gpu-cards__metrics">
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
          <strong>{{ formatMemoryMb(gpu.memory_used) }} / {{ formatMemoryMb(gpu.memory_total) }}</strong>
        </div>
      </div>

      <p v-if="gpu.error" class="import-hardware-gpu-cards__error">{{ gpu.error }}</p>
    </article>
  </div>
</template>

<style scoped>
.import-hardware-gpu-cards {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.import-hardware-gpu-cards__card {
  display: grid;
  gap: 8px;
  padding: 16px;
  border-radius: 20px;
  background: rgba(255, 252, 247, 0.72);
  border: 1px solid rgba(26, 26, 26, 0.05);
}

.import-hardware-gpu-cards__card--disabled {
  border-color: rgba(178, 34, 34, 0.14);
  background: rgba(255, 246, 244, 0.9);
}

.import-hardware-gpu-cards__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.import-hardware-gpu-cards__badge {
  margin-bottom: 6px;
  font-size: 0.74rem;
  color: var(--accent-primary);
}

.import-hardware-gpu-cards__metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.import-hardware-gpu-cards__metrics div {
  display: grid;
  gap: 4px;
}

.import-hardware-gpu-cards__metrics span {
  font-size: 0.78rem;
  line-height: 1.7;
  color: var(--text-muted);
}

.import-hardware-gpu-cards__card strong {
  font-size: 0.94rem;
  line-height: 1.55;
  color: var(--text-primary);
  word-break: break-word;
}

.import-hardware-gpu-cards__error {
  margin: 0;
  font-size: 0.78rem;
  line-height: 1.7;
  color: #8f2d2d;
}

@media (max-width: 960px) {
  .import-hardware-gpu-cards,
  .import-hardware-gpu-cards__metrics {
    grid-template-columns: 1fr;
  }
}
</style>

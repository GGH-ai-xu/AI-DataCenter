<script setup>
import { computed } from 'vue'
import { formatGpuMemoryBytes } from '../../lib/importHardwareFormatting.js'
import { isImportableGpu } from '../../lib/importGpuAvailability.js'

const props = defineProps({
  gpus: { type: Array, default: () => [] },
  modelValue: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:modelValue'])
const selectedSet = computed(() => new Set(props.modelValue.map((value) => Number(value))))

function toggle(index) {
  const gpu = props.gpus.find((item) => Number(item.index) === index)
  if (!isImportableGpu(gpu)) return
  const next = new Set(selectedSet.value)
  if (next.has(index)) next.delete(index)
  else next.add(index)
  emit('update:modelValue', [...next].sort((left, right) => left - right))
}
</script>

<template>
  <div class="import-gpu-grid">
    <div v-if="props.gpus.length" class="import-gpu-grid__list">
      <button
        v-for="gpu in props.gpus"
        :key="gpu.index"
        type="button"
        class="import-gpu-grid__card"
        :class="{
          'import-gpu-grid__card--selected': selectedSet.has(Number(gpu.index)),
          'import-gpu-grid__card--disabled': !isImportableGpu(gpu),
        }"
        :disabled="!isImportableGpu(gpu)"
        @click="toggle(Number(gpu.index))"
      >
        <div class="import-gpu-grid__top">
          <div>
            <div class="import-gpu-grid__badge">GPU {{ gpu.index }}</div>
            <strong>{{ gpu.name }}</strong>
          </div>
          <span
            class="status-badge"
            :class="!isImportableGpu(gpu)
              ? 'status-badge--critical'
              : selectedSet.has(Number(gpu.index))
                ? 'status-badge--ok'
                : 'status-badge--warning'"
          >
            {{ !isImportableGpu(gpu) ? '不可导入' : (selectedSet.has(Number(gpu.index)) ? '已选中' : '点击导入') }}
          </span>
        </div>

        <div class="import-gpu-grid__metrics">
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

        <p v-if="!isImportableGpu(gpu) && gpu.error" class="import-gpu-grid__error">
          {{ gpu.error }}
        </p>
      </button>
    </div>

    <div v-else class="import-gpu-grid__empty">
      当前视图没有可展示的 GPU。
    </div>
  </div>
</template>

<style scoped>
.import-gpu-grid {
  display: grid;
  gap: 16px;
}

.import-gpu-grid__list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.import-gpu-grid__card {
  display: grid;
  gap: 16px;
  padding: 18px;
  border-radius: 22px;
  border: 1px solid var(--import-border, var(--border-color));
  background: var(--import-surface-soft, rgba(255, 255, 255, 0.03));
  text-align: left;
  transition: border-color 0.24s ease, background 0.24s ease, transform 0.24s ease, box-shadow 0.24s ease;
}

.import-gpu-grid__card:hover {
  transform: translateY(-1px);
  border-color: rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.05);
  box-shadow: none;
}

.import-gpu-grid__card--selected {
  border-color: var(--import-border-strong, rgba(94, 106, 210, 0.32));
  background: var(--import-accent-soft, rgba(94, 106, 210, 0.14));
  box-shadow: none;
}

.import-gpu-grid__card--disabled {
  cursor: not-allowed;
  border-color: rgba(178, 34, 34, 0.14);
  background: rgba(255, 246, 244, 0.92);
  box-shadow: none;
}

.import-gpu-grid__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.import-gpu-grid__badge {
  font-size: 0.74rem;
  color: var(--accent-primary);
  margin-bottom: 6px;
}

.import-gpu-grid__metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.import-gpu-grid__metrics div {
  display: grid;
  gap: 5px;
}

.import-gpu-grid__metrics span,
.import-gpu-grid__empty {
  font-size: 0.78rem;
  line-height: 1.7;
  color: var(--text-muted);
}

.import-gpu-grid__error {
  margin: 0;
  font-size: 0.78rem;
  line-height: 1.7;
  color: #8f2d2d;
}

.import-gpu-grid__card strong,
.import-gpu-grid__metrics strong {
  font-size: 0.94rem;
  line-height: 1.55;
  color: var(--text-primary);
  word-break: break-word;
}

@media (max-width: 900px) {
  .import-gpu-grid__list,
  .import-gpu-grid__metrics {
    grid-template-columns: 1fr;
  }
}
</style>

<script setup>
import { computed, ref } from 'vue'
import { selectableGpuIndexes } from '../../lib/importGpuAvailability.js'
import { formatImportedGpuLabel } from '../../lib/importContext.js'
import ImportGpuGrid from './ImportGpuGrid.vue'
import ImportSavedHostSummaryBar from './ImportSavedHostSummaryBar.vue'

const props = defineProps({
  savedHostSummary: { type: Object, default: null },
  gpus: { type: Array, default: () => [] },
  modelValue: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:modelValue'])
const activeView = ref('all')

const selectedSet = computed(() => new Set(props.modelValue.map((value) => Number(value))))
const selectedGpus = computed(() =>
  props.gpus.filter((gpu) => selectedSet.value.has(Number(gpu.index))))
const visibleGpus = computed(() =>
  activeView.value === 'selected' ? selectedGpus.value : props.gpus)
const selectedSummary = computed(() => formatImportedGpuLabel(props.modelValue))

function selectAll() {
  emit('update:modelValue', selectableGpuIndexes(props.gpus))
}

function clearSelection() {
  emit('update:modelValue', [])
}
</script>

<template>
  <section class="import-selection-stage">
    <div class="import-selection-stage__shell">
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
            <strong class="import-selection-stage__count">{{ selectedSummary }}</strong>
          </div>

          <div class="import-selection-stage__toolbar-row">
            <div class="import-selection-stage__view-toggle">
              <button
                type="button"
                class="import-selection-stage__view-button"
                :class="{ 'import-selection-stage__view-button--active': activeView === 'all' }"
                @click="activeView = 'all'"
              >
                全部候选
              </button>
              <button
                type="button"
                class="import-selection-stage__view-button"
                :class="{ 'import-selection-stage__view-button--active': activeView === 'selected' }"
                @click="activeView = 'selected'"
              >
                已选清单
              </button>
            </div>

            <div class="import-selection-stage__actions">
              <button type="button" class="btn-tech" @click="selectAll">全选</button>
              <button type="button" class="btn-tech" @click="clearSelection">清空</button>
            </div>
          </div>
        </section>

        <section class="tech-card import-selection-stage__grid-shell">
          <ImportGpuGrid
            :model-value="props.modelValue"
            :gpus="visibleGpus"
            @update:model-value="emit('update:modelValue', $event)"
          />
        </section>
      </div>

      <aside class="tech-card import-selection-stage__aside">
        <div class="section-title">导入范围摘要</div>
        <div class="import-selection-stage__facts">
          <article class="import-selection-stage__fact">
            <span>当前范围</span>
            <strong>{{ selectedSummary }}</strong>
          </article>
          <article class="import-selection-stage__fact">
            <span>生效说明</span>
            <strong>控制台只显示和治理本次导入选中的卡</strong>
          </article>
          <article class="import-selection-stage__fact">
            <span>进入条件</span>
            <strong>{{ props.modelValue.length > 0 ? '已满足，可直接提交导入' : '至少选择 1 张卡才能进入控制台' }}</strong>
          </article>
        </div>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.import-selection-stage,
.import-selection-stage__main {
  display: grid;
  gap: 16px;
  min-height: 0;
}

.import-selection-stage__shell {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(240px, 0.8fr);
  gap: 16px;
  min-height: 0;
}

.import-selection-stage__toolbar-card,
.import-selection-stage__aside {
  display: grid;
  gap: 16px;
  padding: 20px;
}

.import-selection-stage__toolbar-head,
.import-selection-stage__toolbar-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
}

.import-selection-stage__copy,
.import-selection-stage__fact span {
  font-size: 0.78rem;
  line-height: 1.7;
  color: var(--text-muted);
}

.import-selection-stage__count {
  font-size: 0.98rem;
  line-height: 1.5;
  color: var(--text-primary);
}

.import-selection-stage__view-toggle,
.import-selection-stage__actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.import-selection-stage__view-button {
  min-height: 40px;
  padding: 0 14px;
  border-radius: 999px;
  border: 1px solid rgba(58, 95, 75, 0.12);
  background: rgba(255, 255, 255, 0.82);
  color: var(--text-secondary);
}

.import-selection-stage__view-button--active {
  border-color: rgba(46, 139, 87, 0.18);
  background: rgba(244, 250, 247, 0.88);
  color: var(--text-primary);
}

.import-selection-stage__grid-shell {
  min-height: 0;
  overflow-y: auto;
  padding: 18px;
}

.import-selection-stage__facts {
  display: grid;
  gap: 12px;
}

.import-selection-stage__fact {
  display: grid;
  gap: 8px;
  padding: 16px;
  border-radius: 20px;
  background: rgba(255, 252, 247, 0.72);
  border: 1px solid rgba(26, 26, 26, 0.05);
}

.import-selection-stage__fact strong {
  font-size: 0.94rem;
  line-height: 1.6;
  color: var(--text-primary);
  word-break: break-word;
}

@media (max-width: 960px) {
  .import-selection-stage__shell {
    grid-template-columns: 1fr;
  }
}
</style>

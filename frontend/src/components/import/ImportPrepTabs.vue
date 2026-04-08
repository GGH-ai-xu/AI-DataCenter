<script setup>
const IMPORT_PREP_TAB_ARIA_LABEL = '已保存主机 / 连接来源 / 硬件概览 / 选卡导入'

const props = defineProps({
  modelValue: { type: String, required: true },
  tabs: { type: Array, required: true },
})

const emit = defineEmits(['update:modelValue'])
</script>

<template>
  <div class="import-prep-tabs" :aria-label="IMPORT_PREP_TAB_ARIA_LABEL">
    <button
      v-for="(tab, index) in props.tabs"
      :key="tab.key"
      type="button"
      class="import-prep-tabs__item"
      :class="{ 'import-prep-tabs__item--active': props.modelValue === tab.key }"
      @click="emit('update:modelValue', tab.key)"
    >
      <span class="import-prep-tabs__item-index">{{ index + 1 }}</span>
      <span class="import-prep-tabs__item-label">{{ tab.label }}</span>
    </button>
  </div>
</template>

<style scoped>
.import-prep-tabs {
  display: flex;
  gap: 10px;
  overflow-x: auto;
  padding-bottom: 2px;
}

.import-prep-tabs__item {
  flex: 0 0 auto;
  min-height: 42px;
  padding: 0 16px 0 12px;
  border-radius: 12px;
  border: 1px solid var(--import-border, rgba(255, 255, 255, 0.08));
  background: var(--import-surface-soft, rgba(255, 255, 255, 0.03));
  color: var(--import-text-secondary, var(--text-secondary));
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-weight: 600;
  transition:
    transform 0.24s var(--ease-expo),
    border-color 0.24s ease,
    background 0.24s ease,
    color 0.24s ease;
}

.import-prep-tabs__item:hover {
  transform: translateY(-1px);
  border-color: rgba(255, 255, 255, 0.14);
  color: var(--import-text, var(--text-primary));
}

.import-prep-tabs__item--active {
  border-color: var(--import-border-strong, rgba(94, 106, 210, 0.32));
  background: var(--import-accent-soft, rgba(94, 106, 210, 0.14));
  color: var(--import-text, var(--text-primary));
}

.import-prep-tabs__item-index {
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 7px;
  background: rgba(255, 255, 255, 0.06);
  color: var(--import-text-muted, var(--text-muted));
  font-family: var(--font-seal);
  font-size: 0.72rem;
}

.import-prep-tabs__item--active .import-prep-tabs__item-index {
  background: rgba(255, 255, 255, 0.16);
  color: #eef1ff;
}

.import-prep-tabs__item-label {
  white-space: nowrap;
}
</style>

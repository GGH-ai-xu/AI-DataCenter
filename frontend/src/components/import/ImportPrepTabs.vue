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
      v-for="tab in props.tabs"
      :key="tab.key"
      type="button"
      class="import-prep-tabs__item"
      :class="{ 'import-prep-tabs__item--active': props.modelValue === tab.key }"
      @click="emit('update:modelValue', tab.key)"
    >
      {{ tab.label }}
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
  padding: 0 16px;
  border-radius: 999px;
  border: 1px solid rgba(58, 95, 75, 0.1);
  background: rgba(255, 255, 255, 0.82);
  color: var(--text-secondary);
  transition: border-color 0.24s ease, background 0.24s ease, color 0.24s ease;
}

.import-prep-tabs__item--active {
  border-color: rgba(46, 139, 87, 0.18);
  background: rgba(242, 248, 244, 0.96);
  color: #2f6a46;
}
</style>

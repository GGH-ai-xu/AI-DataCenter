<script setup>
import ImportPrepTabs from './ImportPrepTabs.vue'

const props = defineProps({
  activeTab: { type: String, required: true },
  tabs: { type: Array, required: true },
  footerMessage: { type: String, required: true },
  importBusy: { type: Boolean, required: true },
  importDisabled: { type: Boolean, required: true },
})

const emit = defineEmits(['update:activeTab', 'submit'])
</script>

<template>
  <section class="tech-card import-prep-workbench">
    <ImportPrepTabs
      :model-value="props.activeTab"
      :tabs="props.tabs"
      @update:model-value="emit('update:activeTab', $event)"
    />

    <div class="import-prep-workbench__body">
      <slot />
    </div>

    <div class="import-prep-workbench__footer">
      <div class="import-prep-workbench__status">{{ props.footerMessage }}</div>
      <button
        type="button"
        class="btn-tech btn-tech--primary import-prep-workbench__submit"
        :disabled="props.importBusy || props.importDisabled"
        @click="emit('submit')"
      >
        {{ props.importBusy ? '导入中...' : '导入并进入控制台' }}
      </button>
    </div>
  </section>
</template>

<style scoped>
.import-prep-workbench {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  gap: 16px;
  min-height: 0;
  height: min(880px, calc(100vh - 64px));
  padding: 18px;
}

.import-prep-workbench__body {
  min-height: 0;
  overflow-y: auto;
  padding-right: 4px;
}

.import-prep-workbench__footer {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 16px;
  align-items: center;
  padding-top: 4px;
  border-top: 1px solid rgba(26, 26, 26, 0.06);
}

.import-prep-workbench__status {
  font-size: 0.82rem;
  line-height: 1.7;
  color: var(--text-muted);
}

.import-prep-workbench__submit {
  min-width: 220px;
}

@media (max-width: 1080px) {
  .import-prep-workbench {
    height: auto;
    min-height: 0;
  }
}

@media (max-width: 720px) {
  .import-prep-workbench__footer {
    grid-template-columns: 1fr;
  }

  .import-prep-workbench__submit {
    width: 100%;
  }
}
</style>

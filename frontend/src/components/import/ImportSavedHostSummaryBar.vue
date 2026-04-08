<script setup>
const props = defineProps({
  savedHostSummary: {
    type: Object,
    default: null,
  },
})
</script>

<template>
  <section v-if="props.savedHostSummary" class="import-saved-host-summary">
    <span class="import-saved-host-summary__label">当前复用主机</span>
    <strong class="import-saved-host-summary__title">
      {{ props.savedHostSummary.label }}
    </strong>
    <span class="import-saved-host-summary__target">
      {{ props.savedHostSummary.target }}
    </span>
  </section>
</template>

<style scoped>
.import-saved-host-summary {
  display: grid;
  gap: 6px;
  padding: 16px 18px;
  border-radius: 16px;
  border: 1px solid var(--import-border, var(--border-color));
  background: var(--import-surface-soft, rgba(255, 255, 255, 0.03));
}

.import-saved-host-summary__label {
  font-size: 0.74rem;
  letter-spacing: 0.08em;
  color: var(--import-text-muted, var(--text-muted));
}

.import-saved-host-summary__title,
.import-saved-host-summary__target {
  line-height: 1.6;
  word-break: break-word;
}
</style>

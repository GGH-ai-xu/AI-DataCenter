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
  border-radius: 18px;
  border: 1px solid rgba(58, 95, 75, 0.12);
  background: rgba(244, 250, 247, 0.88);
}

.import-saved-host-summary__label {
  font-size: 0.74rem;
  letter-spacing: 0.08em;
  color: var(--text-muted);
}

.import-saved-host-summary__title,
.import-saved-host-summary__target {
  line-height: 1.6;
  word-break: break-word;
}
</style>

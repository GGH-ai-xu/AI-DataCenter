<script setup>
defineProps({
  model: { type: Object, required: true },
})
</script>

<template>
  <header
    v-if="model.liveText"
    class="agent-workbench-topbar tech-card"
  >
    <p
      class="agent-workbench-topbar__live"
      :class="`agent-workbench-topbar__live--${model.liveTone || 'idle'}`"
    >
      <strong>{{ model.liveLabel || '实时进展' }}</strong>
      <span>{{ model.liveText }}</span>
    </p>
  </header>
</template>

<style scoped>
.agent-workbench-topbar {
  padding: 12px 14px;
  border-radius: 18px;
}

.agent-workbench-topbar__live {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.5;
}

.agent-workbench-topbar__live strong {
  color: var(--text-primary);
  font-weight: 600;
}

.agent-workbench-topbar__live--active strong {
  color: var(--accent-color);
}

.agent-workbench-topbar__live--error strong {
  color: var(--state-danger);
}
</style>

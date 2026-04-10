<script setup>
defineProps({
  status: { type: String, default: 'processing' },
  steps: { type: Array, default: () => [] },
})
</script>

<template>
  <div v-if="steps.length" class="agent-interaction-steps" :data-status="status">
    <div
      v-for="step in steps"
      :key="step.key"
      class="agent-interaction-steps__item"
      :data-state="step.state"
    >
      <span class="agent-interaction-steps__dot" />
      <span>{{ step.label }}</span>
    </div>
  </div>
</template>

<style scoped>
.agent-interaction-steps {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.agent-interaction-steps__item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 32px;
  padding: 0 12px;
  border: 1px solid var(--border-color);
  border-radius: 999px;
  background: color-mix(in srgb, var(--bg-surface) 72%, transparent);
  color: var(--text-secondary);
  font-size: 13px;
}

.agent-interaction-steps__dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--text-muted) 86%, transparent);
}

.agent-interaction-steps__item[data-state='done'] {
  border-color: var(--state-ok-border);
  background: var(--state-ok-bg);
  color: var(--state-ok-text);
}

.agent-interaction-steps__item[data-state='done'] .agent-interaction-steps__dot {
  background: currentColor;
}

.agent-interaction-steps__item[data-state='active'] {
  border-color: var(--border-strong);
  background: color-mix(in srgb, var(--accent-color) 16%, transparent);
  color: var(--text-primary);
}

.agent-interaction-steps__item[data-state='active'] .agent-interaction-steps__dot {
  background: currentColor;
  box-shadow: 0 0 0 4px color-mix(in srgb, currentColor 18%, transparent);
}

.agent-interaction-steps__item[data-state='error'] {
  border-color: var(--state-danger-border);
  background: var(--state-danger-bg);
  color: var(--state-danger-text);
}

.agent-interaction-steps__item[data-state='error'] .agent-interaction-steps__dot {
  background: currentColor;
}
</style>

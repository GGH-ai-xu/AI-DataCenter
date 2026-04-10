<script setup>
import { computed } from 'vue'

const props = defineProps({
  item: { type: Object, required: true },
})

const toneLabel = computed(() => {
  if (props.item.tone === 'llm') return 'LLM'
  if (props.item.tone === 'planner') return '规划'
  if (props.item.tone === 'approval') return '审批'
  return '执行'
})
</script>

<template>
  <article class="tech-card agent-thread-card">
    <span class="agent-thread-card__label" :data-tone="item.tone">{{ toneLabel }}</span>
    <span>{{ item.summary }}</span>
  </article>
</template>

<style scoped>
.agent-thread-card {
  display: grid;
  gap: 8px;
  padding: 14px;
}

.agent-thread-card__label {
  justify-self: flex-start;
  min-height: 22px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid var(--border-color);
  background: color-mix(in srgb, var(--bg-surface) 82%, transparent);
  color: var(--text-muted);
  font-size: 11px;
  line-height: 22px;
  letter-spacing: 0.08em;
}

.agent-thread-card__label[data-tone='llm'] {
  border-color: var(--border-strong);
  color: var(--text-primary);
  background: color-mix(in srgb, var(--accent-color) 16%, transparent);
}
</style>

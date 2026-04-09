<script setup>
defineProps({
  sessions: { type: Array, default: () => [] },
  activeSessionId: { type: String, default: '' },
})

const emit = defineEmits(['select'])
</script>

<template>
  <aside class="agent-session-rail tech-card">
    <button
      v-for="session in sessions"
      :key="session.id"
      type="button"
      class="agent-session-rail__item"
      :class="{ 'agent-session-rail__item--active': session.id === activeSessionId }"
      @click="emit('select', session.id)"
    >
      <span class="agent-session-rail__status" :data-status="session.status"></span>
      <strong>{{ session.title }}</strong>
      <span>{{ session.timeLabel }}</span>
    </button>
  </aside>
</template>

<style scoped>
.agent-session-rail {
  display: grid;
  gap: 10px;
  align-content: start;
  padding: 14px;
}

.agent-session-rail__item {
  display: grid;
  grid-template-columns: 10px minmax(0, 1fr);
  gap: 6px 10px;
  padding: 10px 12px;
  border: 1px solid var(--border-color);
  border-radius: 14px;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.agent-session-rail__item strong,
.agent-session-rail__item span:last-child {
  min-width: 0;
}

.agent-session-rail__item strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-session-rail__item span:last-child {
  grid-column: 2;
  font-size: 0.76rem;
  color: var(--text-muted);
}

.agent-session-rail__item--active {
  border-color: var(--accent-color);
  background: color-mix(in srgb, var(--accent-color) 8%, transparent);
}

.agent-session-rail__status {
  width: 10px;
  height: 10px;
  margin-top: 4px;
  border-radius: 999px;
  background: var(--text-muted);
}

.agent-session-rail__status[data-status='running'] {
  background: var(--state-info-text, #3b82f6);
}

.agent-session-rail__status[data-status='awaiting_approval'] {
  background: var(--state-warning-text);
}

.agent-session-rail__status[data-status='completed'] {
  background: var(--state-ok-text);
}

.agent-session-rail__status[data-status='failed'],
.agent-session-rail__status[data-status='aborted'] {
  background: var(--state-danger-text);
}
</style>

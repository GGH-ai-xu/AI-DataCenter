<script setup>
defineProps({
  sessions: { type: Array, default: () => [] },
  activeSessionId: { type: String, default: '' },
})

const emit = defineEmits(['select', 'create', 'delete'])
</script>

<template>
  <aside class="agent-session-rail">
    <header class="agent-session-rail__head">
      <div>
        <h3>会话栏</h3>
        <p>最近会话</p>
      </div>
      <button
        type="button"
        class="agent-session-rail__create"
        @click="emit('create')"
      >
        新建会话
      </button>
    </header>
    <div v-if="!sessions.length" class="agent-session-rail__empty">
      <strong>暂无历史会话</strong>
      <span>执行或追问后，会在这里沉淀会话记录</span>
    </div>
    <div v-else class="agent-session-rail__list">
      <article
        v-for="session in sessions"
        :key="session.id"
        class="agent-session-rail__item"
        :class="{ 'agent-session-rail__item--active': session.id === activeSessionId }"
      >
        <span class="agent-session-rail__status" :data-status="session.status"></span>
        <button
          type="button"
          class="agent-session-rail__select"
          @click="emit('select', session.id)"
        >
          <strong>{{ session.title }}</strong>
          <span>{{ session.timeLabel }}</span>
        </button>
        <button
          type="button"
          class="agent-session-rail__delete"
          :disabled="session.canDelete === false"
          :title="session.canDelete === false ? '运行中会话暂不允许删除' : '删除会话'"
          aria-label="删除会话"
          @click="emit('delete', session.id)"
        >
          删除
        </button>
      </article>
    </div>
  </aside>
</template>

<style scoped>
.agent-session-rail {
  display: grid;
  gap: 14px;
  align-content: start;
}

.agent-session-rail__head h3,
.agent-session-rail__head p,
.agent-session-rail__empty strong,
.agent-session-rail__empty span {
  margin: 0;
}

.agent-session-rail__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.agent-session-rail__head h3 {
  font-size: 0.95rem;
  color: var(--text-primary);
}

.agent-session-rail__head p,
.agent-session-rail__empty span {
  margin-top: 4px;
  font-size: 0.8rem;
  line-height: 1.6;
  color: var(--text-muted);
}

.agent-session-rail__create {
  flex-shrink: 0;
  border: 1px solid var(--border-color);
  border-radius: 999px;
  background: transparent;
  color: var(--text-secondary);
  padding: 7px 12px;
  cursor: pointer;
}

.agent-session-rail__empty {
  display: grid;
  gap: 6px;
  padding: 14px;
  border: 1px dashed var(--border-color);
  border-radius: 16px;
  background: color-mix(in srgb, var(--bg-card) 74%, transparent);
}

.agent-session-rail__list {
  display: grid;
  gap: 10px;
}

.agent-session-rail__item {
  display: grid;
  grid-template-columns: 10px minmax(0, 1fr) auto;
  gap: 6px 10px;
  align-items: center;
  padding: 10px 10px 10px 12px;
  border: 1px solid var(--border-color);
  border-radius: 14px;
  background: transparent;
}

.agent-session-rail__select {
  display: grid;
  gap: 6px;
  min-width: 0;
  border: 0;
  background: transparent;
  color: inherit;
  padding: 0;
  text-align: left;
  cursor: pointer;
}

.agent-session-rail__select strong,
.agent-session-rail__select span {
  min-width: 0;
}

.agent-session-rail__select strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-session-rail__select span {
  font-size: 0.76rem;
  color: var(--text-muted);
}

.agent-session-rail__item--active {
  border-color: var(--accent-color);
  background: color-mix(in srgb, var(--accent-color) 8%, transparent);
}

.agent-session-rail__delete {
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: var(--text-muted);
  padding: 6px 8px;
  cursor: pointer;
}

.agent-session-rail__delete:hover:not(:disabled) {
  background: color-mix(in srgb, var(--state-danger-text) 10%, transparent);
  color: var(--state-danger-text);
}

.agent-session-rail__delete:disabled {
  opacity: 0.45;
  cursor: not-allowed;
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

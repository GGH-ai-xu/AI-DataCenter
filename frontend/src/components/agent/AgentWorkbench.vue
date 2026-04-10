<script setup>
import AgentComposer from './AgentComposer.vue'
import AgentSessionRail from './AgentSessionRail.vue'
import AgentThread from './AgentThread.vue'
import AgentWorkbenchTopbar from './AgentWorkbenchTopbar.vue'

defineProps({
  sessions: { type: Array, default: () => [] },
  activeSessionId: { type: String, default: '' },
  topbar: { type: Object, required: true },
  leadMessage: { type: Object, default: null },
  interactions: { type: Array, default: () => [] },
  composerText: { type: String, required: true },
  busy: { type: Boolean, default: false },
})

const emit = defineEmits([
  'createSession',
  'selectSession',
  'deleteSession',
  'update:composerText',
  'submit',
  'approve',
  'reject',
])
</script>

<template>
  <section class="agent-workbench">
    <div class="agent-workbench__rail-card tech-card">
      <AgentSessionRail
        :sessions="sessions"
        :active-session-id="activeSessionId"
        @create="emit('createSession')"
        @select="emit('selectSession', $event)"
        @delete="emit('deleteSession', $event)"
      />
    </div>
    <div class="agent-workbench__chat-card tech-card">
      <div class="agent-workbench__topbar-shell">
        <AgentWorkbenchTopbar :model="topbar" />
      </div>
      <div class="agent-workbench__thread-shell">
        <AgentThread
          :lead-message="leadMessage"
          :interactions="interactions"
          @approve="emit('approve', $event)"
          @reject="emit('reject', $event)"
        />
      </div>
      <div class="agent-workbench__composer-shell">
        <AgentComposer
          :input-text="composerText"
          :disabled="busy"
          @update:inputText="emit('update:composerText', $event)"
          @submit="emit('submit')"
        />
      </div>
    </div>
  </section>
</template>

<style scoped>
.agent-workbench {
  display: grid;
  grid-template-columns: 216px minmax(0, 1fr);
  gap: 16px;
  align-items: stretch;
}

.agent-workbench__rail-card,
.agent-workbench__chat-card {
  display: grid;
  gap: 14px;
  padding: 16px;
}

.agent-workbench__chat-card {
  grid-template-rows: auto minmax(0, 1fr) auto;
  gap: 0;
  height: clamp(560px, calc(100vh - 220px), 760px);
  min-height: 0;
}

.agent-workbench__topbar-shell {
  grid-row: 1;
  min-height: 0;
}

.agent-workbench__thread-shell {
  grid-row: 2;
  min-height: 0;
  overflow-y: auto;
  padding-top: 14px;
  padding-right: 2px;
  padding-bottom: 18px;
}

.agent-workbench__composer-shell {
  grid-row: 3;
  padding-top: 14px;
  border-top: 1px solid color-mix(in srgb, var(--border-color) 88%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--bg-card) 26%, transparent) 0%,
      color-mix(in srgb, var(--bg-card) 94%, transparent) 100%
    );
}

@media (max-width: 1080px) {
  .agent-workbench {
    grid-template-columns: 1fr;
  }

  .agent-workbench__chat-card {
    height: auto;
  }
}
</style>

<script setup>
import AgentComposer from './AgentComposer.vue'
import AgentSessionRail from './AgentSessionRail.vue'
import AgentThread from './AgentThread.vue'
import AgentWorkbenchTopbar from './AgentWorkbenchTopbar.vue'

defineProps({
  sessions: { type: Array, default: () => [] },
  activeSessionId: { type: String, default: '' },
  topbar: { type: Object, required: true },
  threadItems: { type: Array, default: () => [] },
  composerText: { type: String, required: true },
  quickPrompts: { type: Array, default: () => [] },
  busy: { type: Boolean, default: false },
})

const emit = defineEmits([
  'selectSession',
  'update:composerText',
  'submit',
  'usePrompt',
  'approve',
  'reject',
  'chooseRoute',
])
</script>

<template>
  <section class="agent-workbench">
    <AgentSessionRail
      :sessions="sessions"
      :active-session-id="activeSessionId"
      @select="emit('selectSession', $event)"
    />
    <div class="agent-workbench__main">
      <AgentWorkbenchTopbar :model="topbar" />
      <AgentThread
        :items="threadItems"
        @approve="emit('approve', $event)"
        @reject="emit('reject', $event)"
        @choose-route="emit('chooseRoute', $event)"
      />
      <AgentComposer
        :input-text="composerText"
        :quick-prompts="quickPrompts"
        :disabled="busy"
        @update:inputText="emit('update:composerText', $event)"
        @submit="emit('submit')"
        @usePrompt="emit('usePrompt', $event)"
      />
    </div>
  </section>
</template>

<style scoped>
.agent-workbench {
  display: grid;
  grid-template-columns: minmax(220px, 280px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.agent-workbench__main {
  display: grid;
  gap: 14px;
}

@media (max-width: 1080px) {
  .agent-workbench {
    grid-template-columns: 1fr;
  }
}
</style>

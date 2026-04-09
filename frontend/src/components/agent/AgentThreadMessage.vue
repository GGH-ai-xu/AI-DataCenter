<script setup>
import AgentChatMessageBody from './AgentChatMessageBody.vue'

defineProps({
  item: { type: Object, required: true },
})
</script>

<template>
  <article class="agent-thread-message tech-card" :data-role="item.role">
    <AgentChatMessageBody :message="{ role: item.role, content: item.content }" />
  </article>
</template>

<style scoped>
.agent-thread-message {
  padding: 14px;
}

.agent-thread-message[data-role='user'] {
  border-color: color-mix(in srgb, var(--accent-color) 40%, var(--border-color));
}
</style>

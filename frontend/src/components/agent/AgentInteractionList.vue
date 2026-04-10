<script setup>
import AgentThreadMessage from './AgentThreadMessage.vue'
import AgentInteractionCard from './AgentInteractionCard.vue'

defineProps({
  leadMessage: { type: Object, default: null },
  interactions: { type: Array, default: () => [] },
})

const emit = defineEmits(['approve', 'reject'])
</script>

<template>
  <section class="agent-interaction-list">
    <AgentThreadMessage v-if="leadMessage" :item="leadMessage" />
    <AgentInteractionCard
      v-for="interaction in interactions"
      :key="interaction.id"
      :interaction="interaction"
      @approve="emit('approve', $event)"
      @reject="emit('reject', $event)"
    />
  </section>
</template>

<style scoped>
.agent-interaction-list {
  display: grid;
  gap: 12px;
  align-content: start;
}
</style>

<script setup>
import AgentInteractionList from './AgentInteractionList.vue'

defineProps({
  leadMessage: { type: Object, default: null },
  interactions: { type: Array, default: () => [] },
})

const emit = defineEmits(['approve', 'reject'])
</script>

<template>
  <AgentInteractionList
    :lead-message="leadMessage"
    :interactions="interactions"
    @approve="emit('approve', $event)"
    @reject="emit('reject', $event)"
  />
</template>

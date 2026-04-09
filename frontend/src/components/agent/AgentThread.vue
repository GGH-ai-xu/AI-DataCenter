<script setup>
import AgentThreadItem from './AgentThreadItem.vue'

defineProps({
  items: { type: Array, default: () => [] },
})

const emit = defineEmits(['approve', 'reject', 'chooseRoute'])
</script>

<template>
  <section class="agent-thread">
    <AgentThreadItem
      v-for="item in items"
      :key="item.id"
      :item="item"
      @approve="emit('approve', $event)"
      @reject="emit('reject', $event)"
      @choose-route="emit('chooseRoute', $event)"
    />
  </section>
</template>

<style scoped>
.agent-thread {
  display: grid;
  gap: 12px;
  align-content: start;
}
</style>

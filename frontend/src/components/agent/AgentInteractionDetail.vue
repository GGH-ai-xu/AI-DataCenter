<script setup>
import AgentThreadApprovalCard from './AgentThreadApprovalCard.vue'
import AgentThreadErrorCard from './AgentThreadErrorCard.vue'
import AgentThreadPlanCard from './AgentThreadPlanCard.vue'
import AgentThreadResultCard from './AgentThreadResultCard.vue'
import AgentThreadToolEventCard from './AgentThreadToolEventCard.vue'

defineProps({
  interaction: { type: Object, required: true },
})

const emit = defineEmits(['approve', 'reject'])
</script>

<template>
  <section v-if="interaction.runtimeCards.length" class="agent-interaction-detail">
    <component
      :is="card.kind === 'plan_card'
        ? AgentThreadPlanCard
        : card.kind === 'approval_card'
          ? AgentThreadApprovalCard
          : card.kind === 'result_card'
            ? AgentThreadResultCard
            : card.kind === 'error_card'
              ? AgentThreadErrorCard
              : AgentThreadToolEventCard"
      v-for="card in interaction.runtimeCards"
      :key="card.id"
      :item="card"
      @approve="emit('approve', $event)"
      @reject="emit('reject', $event)"
    />
  </section>
</template>

<style scoped>
.agent-interaction-detail {
  display: grid;
  gap: 10px;
  padding-top: 4px;
}
</style>

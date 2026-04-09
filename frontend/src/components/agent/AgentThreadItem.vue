<script setup>
import AgentThreadApprovalCard from './AgentThreadApprovalCard.vue'
import AgentThreadErrorCard from './AgentThreadErrorCard.vue'
import AgentThreadMessage from './AgentThreadMessage.vue'
import AgentThreadPlanCard from './AgentThreadPlanCard.vue'
import AgentThreadResultCard from './AgentThreadResultCard.vue'
import AgentThreadRouteConfirmCard from './AgentThreadRouteConfirmCard.vue'
import AgentThreadToolEventCard from './AgentThreadToolEventCard.vue'

defineProps({
  item: { type: Object, required: true },
})

const emit = defineEmits(['approve', 'reject', 'chooseRoute'])
</script>

<template>
  <AgentThreadMessage
    v-if="item.kind === 'user_message' || item.kind === 'assistant_message'"
    :item="item"
  />
  <AgentThreadPlanCard v-else-if="item.kind === 'plan_card'" :item="item" />
  <AgentThreadApprovalCard
    v-else-if="item.kind === 'approval_card'"
    :item="item"
    @approve="emit('approve', $event)"
    @reject="emit('reject', $event)"
  />
  <AgentThreadToolEventCard v-else-if="item.kind === 'tool_event'" :item="item" />
  <AgentThreadResultCard v-else-if="item.kind === 'result_card'" :item="item" />
  <AgentThreadErrorCard v-else-if="item.kind === 'error_card'" :item="item" />
  <AgentThreadRouteConfirmCard
    v-else
    :item="item"
    @choose="emit('chooseRoute', $event)"
  />
</template>

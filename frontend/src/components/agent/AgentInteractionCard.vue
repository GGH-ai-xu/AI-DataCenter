<script setup>
import { computed, ref } from 'vue'

import AgentChatMessageBody from './AgentChatMessageBody.vue'
import AgentInteractionDetail from './AgentInteractionDetail.vue'
import AgentInteractionSteps from './AgentInteractionSteps.vue'

const props = defineProps({
  interaction: { type: Object, required: true },
})

const emit = defineEmits(['approve', 'reject'])
const expanded = ref(false)

const statusLabel = computed(() => {
  if (props.interaction.status === 'awaiting_approval') return '待审批'
  if (props.interaction.status === 'completed') return '已完成'
  if (props.interaction.status === 'failed') return '失败'
  return '处理中'
})

const statusClass = computed(() => {
  if (props.interaction.status === 'awaiting_approval') return 'status-badge--warning'
  if (props.interaction.status === 'completed') return 'status-badge--ok'
  if (props.interaction.status === 'failed') return 'status-badge--critical'
  return ''
})

const hasDetails = computed(() => props.interaction.runtimeCards.length > 0)
const toggleLabel = computed(() => (expanded.value ? '收起步骤' : '展开步骤'))
</script>

<template>
  <article class="agent-interaction-card tech-card" :data-status="interaction.status">
    <header class="agent-interaction-card__header">
      <div class="agent-interaction-card__prompt">
        <span class="agent-interaction-card__label">本次输入</span>
        <p>{{ interaction.userMessage.content }}</p>
      </div>
      <span class="status-badge" :class="statusClass">{{ statusLabel }}</span>
    </header>

    <section v-if="interaction.assistantReply" class="agent-interaction-card__reply">
      <span class="agent-interaction-card__label">助手摘要</span>
      <AgentChatMessageBody
        :message="{ role: 'assistant', content: interaction.assistantReply }"
      />
    </section>

    <AgentInteractionSteps :steps="interaction.steps" :status="interaction.status" />

    <footer v-if="hasDetails" class="agent-interaction-card__footer">
      <button
        type="button"
        class="agent-interaction-card__toggle"
        @click="expanded = !expanded"
      >
        {{ toggleLabel }}
      </button>
    </footer>

    <AgentInteractionDetail
      v-if="expanded"
      :interaction="interaction"
      @approve="emit('approve', $event)"
      @reject="emit('reject', $event)"
    />
  </article>
</template>

<style scoped>
.agent-interaction-card {
  display: grid;
  gap: 14px;
  padding: 16px 18px;
}

.agent-interaction-card__header {
  display: flex;
  gap: 12px;
  justify-content: space-between;
  align-items: flex-start;
}

.agent-interaction-card__prompt {
  min-width: 0;
  display: grid;
  gap: 6px;
}

.agent-interaction-card__label {
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.agent-interaction-card__prompt p {
  margin: 0;
  color: var(--text-primary);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.agent-interaction-card__reply {
  display: grid;
  gap: 8px;
  padding: 12px 14px;
  border-radius: 14px;
  background: color-mix(in srgb, var(--bg-surface) 82%, transparent);
  border: 1px solid color-mix(in srgb, var(--border-color) 88%, transparent);
}

.agent-interaction-card__footer {
  display: flex;
  justify-content: flex-start;
}

.agent-interaction-card__toggle {
  border: 1px solid var(--border-color);
  border-radius: 999px;
  background: transparent;
  color: var(--text-secondary);
  min-height: 34px;
  padding: 0 14px;
  cursor: pointer;
  transition: border-color 160ms var(--ease-expo), color 160ms var(--ease-expo), background 160ms var(--ease-expo);
}

.agent-interaction-card__toggle:hover {
  border-color: var(--border-hover);
  color: var(--text-primary);
  background: color-mix(in srgb, var(--bg-surface) 82%, transparent);
}

.agent-interaction-card[data-status='failed'] {
  border-color: var(--state-danger-border);
}

@media (max-width: 720px) {
  .agent-interaction-card__header {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>

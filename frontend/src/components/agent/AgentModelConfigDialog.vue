<script setup>
import { onBeforeUnmount, onMounted } from 'vue'

import AgentModelConfigPane from './AgentModelConfigPane.vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  llmReady: { type: Boolean, default: false },
  llmBusy: { type: Boolean, default: false },
  llmNotice: { type: String, default: '' },
  llmFeedback: { type: Object, default: null },
  llmForm: { type: Object, required: true },
  hasStoredKey: { type: Boolean, default: false },
  savedKeyHint: { type: String, default: '' },
  llmSourceLabel: { type: String, default: '' },
  llmUpdatedAt: { type: String, default: '' },
  canTestLlm: { type: Boolean, default: false },
  canSaveLlm: { type: Boolean, default: false },
})

const emit = defineEmits(['close', 'runTest', 'save'])

function handleKeydown(event) {
  if (!props.open || event.key !== 'Escape') return
  emit('close')
}

onMounted(() => window.addEventListener('keydown', handleKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', handleKeydown))
</script>

<template>
  <div
    v-if="open"
    class="agent-model-config-dialog"
    role="presentation"
    @click.self="emit('close')"
  >
    <section
      class="agent-model-config-dialog__panel tech-card"
      role="dialog"
      aria-modal="true"
      aria-label="模型配置"
    >
      <header class="agent-model-config-dialog__head">
        <div>
          <strong>模型配置</strong>
          <span>配置当前 AI 助手的 LLM 接入</span>
        </div>
        <button
          type="button"
          class="agent-model-config-dialog__close"
          @click="emit('close')"
        >
          关闭
        </button>
      </header>
      <div class="agent-model-config-dialog__body">
        <AgentModelConfigPane
          :llm-ready="llmReady"
          :llm-busy="llmBusy"
          :llm-notice="llmNotice"
          :llm-feedback="llmFeedback"
          :llm-form="llmForm"
          :has-stored-key="hasStoredKey"
          :saved-key-hint="savedKeyHint"
          :llm-source-label="llmSourceLabel"
          :llm-updated-at="llmUpdatedAt"
          :can-test-llm="canTestLlm"
          :can-save-llm="canSaveLlm"
          @run-test="$emit('runTest')"
          @save="$emit('save')"
        />
      </div>
    </section>
  </div>
</template>

<style scoped>
.agent-model-config-dialog {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: grid;
  place-items: center;
  padding: 24px;
  background: color-mix(in srgb, var(--bg-overlay, #060816) 76%, transparent);
  backdrop-filter: blur(12px);
}

.agent-model-config-dialog__panel {
  width: min(720px, 100%);
  max-height: min(88vh, 920px);
  display: grid;
  gap: 14px;
  padding: 18px;
  overflow: hidden;
}

.agent-model-config-dialog__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.agent-model-config-dialog__head strong,
.agent-model-config-dialog__head span {
  display: block;
}

.agent-model-config-dialog__head strong {
  font-size: 1rem;
  color: var(--text-primary);
}

.agent-model-config-dialog__head span {
  margin-top: 4px;
  font-size: 0.8rem;
  color: var(--text-muted);
}

.agent-model-config-dialog__close {
  border: 1px solid var(--border-color);
  border-radius: 999px;
  background: transparent;
  color: var(--text-secondary);
  padding: 8px 14px;
  cursor: pointer;
}

.agent-model-config-dialog__body {
  min-height: 0;
  overflow: auto;
}

@media (max-width: 720px) {
  .agent-model-config-dialog {
    padding: 14px;
  }

  .agent-model-config-dialog__panel {
    max-height: 92vh;
    padding: 14px;
  }

  .agent-model-config-dialog__head {
    flex-direction: column;
  }
}
</style>

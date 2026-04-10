<script setup>
defineProps({
  llmReady: {
    type: Boolean,
    default: false,
  },
  llmBusy: {
    type: Boolean,
    default: false,
  },
  llmNotice: {
    type: String,
    default: '',
  },
  llmFeedback: {
    type: Object,
    default: null,
  },
  llmForm: {
    type: Object,
    required: true,
  },
  hasStoredKey: {
    type: Boolean,
    default: false,
  },
  savedKeyHint: {
    type: String,
    default: '',
  },
  llmSourceLabel: {
    type: String,
    default: '',
  },
  llmUpdatedAt: {
    type: String,
    default: '',
  },
  canTestLlm: {
    type: Boolean,
    default: false,
  },
  canSaveLlm: {
    type: Boolean,
    default: false,
  },
})

defineEmits(['runTest', 'save'])
</script>

<template>
  <section class="agent-model-config-pane tech-card">
    <header class="agent-model-config-pane__head">
      <h3>LLM 模型配置</h3>
      <span>{{ llmSourceLabel }} · 最近保存 {{ llmUpdatedAt }}</span>
    </header>

    <div v-if="!llmReady" class="agent-model-config-pane__notice agent-model-config-pane__notice--warning">
      {{ llmNotice }}
    </div>

    <div class="agent-model-config-pane__grid">
      <label class="agent-model-config-pane__field">
        <span>Base URL</span>
        <input v-model="llmForm.base_url" type="text" placeholder="例如：https://api.deepseek.com/v1" />
      </label>
      <label class="agent-model-config-pane__field">
        <span>Model</span>
        <input v-model="llmForm.model" type="text" placeholder="可留空，测试时自动探测" />
      </label>
      <label class="agent-model-config-pane__field agent-model-config-pane__field--full">
        <span>API Key</span>
        <input
          v-model="llmForm.api_key"
          type="password"
          :placeholder="hasStoredKey ? '留空则继续使用已保存 Key' : '输入 OpenAI 兼容接口密钥'"
        />
      </label>
    </div>

    <div class="agent-model-config-pane__meta">{{ savedKeyHint }}</div>

    <label v-if="hasStoredKey" class="ai-check">
      <input v-model="llmForm.keep_existing_key" type="checkbox" />
      <span>留空时继续使用已保存 Key</span>
    </label>

    <label class="ai-check">
      <input v-model="llmForm.enabled" type="checkbox" />
      <span>保存后立即启用 AI 助手</span>
    </label>

    <div class="agent-model-config-pane__actions">
      <button type="button" class="btn-tech" :disabled="llmBusy || !canTestLlm" @click="$emit('runTest')">
        {{ llmBusy ? '处理中...' : '测试连接' }}
      </button>
      <button type="button" class="btn-tech btn-tech--primary" :disabled="llmBusy || !canSaveLlm" @click="$emit('save')">
        {{ llmBusy ? '处理中...' : '保存并生效' }}
      </button>
    </div>

    <div
      v-if="llmFeedback"
      class="agent-model-config-pane__notice"
      :class="llmFeedback.type === 'success' ? 'agent-model-config-pane__notice--success' : 'agent-model-config-pane__notice--danger'"
    >
      {{ llmFeedback.text }}
    </div>
  </section>
</template>

<style scoped>
.agent-model-config-pane {
  display: grid;
  gap: 14px;
  padding: 20px 22px;
}

.agent-model-config-pane__head,
.agent-model-config-pane__actions {
  display: flex;
  gap: 12px;
}

.agent-model-config-pane__head {
  align-items: flex-end;
  justify-content: space-between;
}

.agent-model-config-pane__head h3 {
  margin: 0;
  color: var(--text-primary);
}

.agent-model-config-pane__head span,
.agent-model-config-pane__meta {
  font-size: 0.76rem;
  line-height: 1.7;
  color: var(--text-muted);
}

.agent-model-config-pane__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.agent-model-config-pane__field {
  display: grid;
  gap: 8px;
}

.agent-model-config-pane__field span {
  font-size: 0.78rem;
  color: var(--text-secondary);
}

.agent-model-config-pane__field--full {
  grid-column: 1 / -1;
}

.agent-model-config-pane__notice {
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  font-size: 0.78rem;
  line-height: 1.7;
}

.agent-model-config-pane__notice--warning {
  background: var(--state-warning-bg);
  border-color: var(--state-warning-border);
  color: var(--state-warning-text);
}

.agent-model-config-pane__notice--success {
  background: var(--state-ok-bg);
  border-color: var(--state-ok-border);
  color: var(--state-ok-text);
}

.agent-model-config-pane__notice--danger {
  background: var(--state-danger-bg);
  border-color: var(--state-danger-border);
  color: var(--state-danger-text);
}

@media (max-width: 960px) {
  .agent-model-config-pane__grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .agent-model-config-pane__head,
  .agent-model-config-pane__actions {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>

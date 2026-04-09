<script setup>
import { nextTick, ref, watch } from 'vue'

import AgentChatMessageBody from './AgentChatMessageBody.vue'

const props = defineProps({
  messages: {
    type: Array,
    default: () => [],
  },
  inputText: {
    type: String,
    required: true,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  llmReady: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['update:inputText', 'submit', 'useSuggestion'])
const chatContainer = ref(null)

function scrollBottom() {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

function handleKeydown(event) {
  if (event.key !== 'Enter' || event.shiftKey) return
  event.preventDefault()
  emit('submit')
}

watch(
  () => [props.messages.length, props.loading],
  scrollBottom,
  { immediate: true },
)
</script>

<template>
  <section class="agent-chat-pane tech-card">
    <header class="agent-chat-pane__head">
      <h3>AI 问答助手</h3>
      <span>解释当前 GPU 状态、能耗与治理策略</span>
    </header>

    <div ref="chatContainer" class="agent-chat-pane__messages">
      <article
        v-for="(msg, index) in messages"
        :key="index"
        class="agent-chat-pane__message"
        :class="msg.role === 'user' ? 'agent-chat-pane__message--user' : 'agent-chat-pane__message--assistant'"
      >
        <div class="agent-chat-pane__avatar">{{ msg.role === 'user' ? '我' : '智' }}</div>
        <div class="agent-chat-pane__body">
          <AgentChatMessageBody :message="msg" />
          <div v-if="msg.suggestions?.length" class="agent-chat-pane__suggestions">
            <button
              v-for="(suggestion, suggestionIndex) in msg.suggestions"
              :key="suggestionIndex"
              type="button"
              class="btn-tech"
              @click="emit('useSuggestion', suggestion)"
            >
              {{ suggestion }}
            </button>
          </div>
        </div>
      </article>
    </div>

    <div class="agent-chat-pane__composer">
      <textarea
        :value="inputText"
        rows="2"
        :disabled="!llmReady"
        :placeholder="llmReady ? '输入问题，如：当前集群功耗为何偏高？' : '请先配置并启用 LLM 后再使用 AI 问答'"
        @input="emit('update:inputText', $event.target.value)"
        @keydown="handleKeydown"
      />
      <button
        type="button"
        class="btn-tech btn-tech--primary"
        :disabled="loading || !inputText.trim() || !llmReady"
        @click="emit('submit')"
      >
        {{ loading ? '发送中...' : '发送' }}
      </button>
    </div>
  </section>
</template>

<style scoped>
.agent-chat-pane {
  display: grid;
  gap: 14px;
  padding: 20px 22px;
}

.agent-chat-pane__head,
.agent-chat-pane__composer {
  display: flex;
  gap: 12px;
}

.agent-chat-pane__head {
  align-items: flex-end;
  justify-content: space-between;
}

.agent-chat-pane__head h3 {
  margin: 0;
  color: var(--text-primary);
}

.agent-chat-pane__head span {
  font-size: 0.76rem;
  color: var(--text-muted);
}

.agent-chat-pane__messages {
  display: grid;
  gap: 12px;
  max-height: calc(100vh - 280px);
  overflow: auto;
}

.agent-chat-pane__message {
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr);
  gap: 12px;
  align-items: start;
}

.agent-chat-pane__avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.76rem;
}

.agent-chat-pane__body {
  padding: 12px 14px;
  border-radius: 16px;
  background: var(--bg-card);
  color: var(--text-secondary);
  line-height: 1.7;
}

.agent-chat-pane__message--user .agent-chat-pane__body {
  background: var(--bg-strong);
  color: var(--text-primary);
}

.agent-chat-pane__suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.agent-chat-pane__suggestions .btn-tech {
  font-size: 0.72rem;
}

.agent-chat-pane__composer {
  align-items: flex-end;
}

.agent-chat-pane__composer textarea {
  width: 100%;
  min-height: 64px;
  border-radius: 12px;
  resize: vertical;
}

@media (max-width: 960px) {
  .agent-chat-pane__messages {
    max-height: none;
  }
}

@media (max-width: 720px) {
  .agent-chat-pane__head,
  .agent-chat-pane__composer {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>

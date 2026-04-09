<script setup>
import { computed } from 'vue'

import { renderAssistantMarkdown } from '../../lib/agentMarkdown.js'

const props = defineProps({
  message: {
    type: Object,
    required: true,
  },
})

const isAssistant = computed(() => props.message.role === 'assistant')
const rendered = computed(() => {
  if (!isAssistant.value) {
    return {
      mode: 'text',
      html: '',
      error: '',
    }
  }
  return renderAssistantMarkdown(props.message.content || '')
})
</script>

<template>
  <div
    v-if="message.role !== 'assistant'"
    class="agent-chat-message-body agent-chat-message-body--plain"
  >
    {{ message.content }}
  </div>
  <div v-else class="agent-chat-message-body agent-chat-message-body--markdown">
    <div
      class="agent-chat-markdown"
      :class="{ 'agent-chat-markdown--fallback': rendered.mode === 'text' }"
      v-html="rendered.html"
    />
    <p
      v-if="rendered.mode === 'text' && rendered.error"
      class="agent-chat-message-body__fallback-note"
    >
      Markdown 渲染失败，已回退为纯文本。
    </p>
  </div>
</template>

<style scoped>
.agent-chat-message-body--plain {
  white-space: pre-wrap;
}

.agent-chat-markdown {
  display: grid;
  gap: 10px;
}

.agent-chat-markdown :deep(h1),
.agent-chat-markdown :deep(h2),
.agent-chat-markdown :deep(h3) {
  margin: 0;
  color: var(--text-primary);
  line-height: 1.35;
}

.agent-chat-markdown :deep(h1) {
  font-size: 1.18rem;
}

.agent-chat-markdown :deep(h2) {
  font-size: 1.04rem;
}

.agent-chat-markdown :deep(h3) {
  font-size: 0.94rem;
}

.agent-chat-markdown :deep(p),
.agent-chat-markdown :deep(li) {
  margin: 0;
  line-height: 1.75;
}

.agent-chat-markdown :deep(ul),
.agent-chat-markdown :deep(ol) {
  margin: 0;
  padding-left: 1.2rem;
}

.agent-chat-markdown :deep(blockquote) {
  margin: 0;
  padding-left: 12px;
  border-left: 3px solid var(--border-color);
  color: var(--text-secondary);
}

.agent-chat-markdown :deep(pre) {
  margin: 0;
  padding: 12px 14px;
  border-radius: 12px;
  overflow: auto;
  background: rgba(15, 23, 42, 0.08);
}

.agent-chat-markdown :deep(code) {
  font-family: 'IBM Plex Mono', 'JetBrains Mono', monospace;
  font-size: 0.84em;
}

.agent-chat-markdown :deep(table) {
  width: 100%;
  border-collapse: collapse;
  display: block;
  overflow-x: auto;
}

.agent-chat-markdown :deep(th),
.agent-chat-markdown :deep(td) {
  padding: 8px 10px;
  border: 1px solid var(--border-color);
  text-align: left;
  white-space: nowrap;
}

.agent-chat-markdown :deep(strong) {
  color: var(--text-primary);
}

.agent-chat-message-body__fallback-note {
  margin: 8px 0 0;
  font-size: 0.72rem;
  color: var(--text-muted);
}
</style>

<script setup>
/**
 * AIAssistant.vue - AI智能问答助手
 * 基于实时GPU数据的LLM对话，提供能耗优化建议
 */
import { ref, nextTick } from 'vue'
import { aiChat } from '../services/api'

const messages = ref([
  { role: 'assistant', content: '你好！我是AI数据中心能耗优化助手。我可以基于当前GPU实时状态为你分析能耗情况并给出优化建议。\n\n试试问我：\n- 当前哪个GPU功耗最高？\n- 集群整体能耗如何优化？\n- 帮我制定一个削峰填谷策略' }
])
const input = ref('')
const loading = ref(false)
const chatContainer = ref(null)

async function sendMessage() {
  const msg = input.value.trim()
  if (!msg || loading.value) return

  messages.value.push({ role: 'user', content: msg })
  input.value = ''
  loading.value = true
  scrollBottom()

  try {
    const { data } = await aiChat(msg)
    messages.value.push({
      role: 'assistant',
      content: data.reply,
      suggestions: data.suggestions || [],
    })
  } catch (e) {
    messages.value.push({
      role: 'assistant',
      content: 'AI服务暂时不可用，请检查LLM配置。',
    })
  }

  loading.value = false
  scrollBottom()
}

function useSuggestion(text) {
  input.value = text
  sendMessage()
}

function scrollBottom() {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}
</script>

<template>
  <div class="ai-page">
    <div class="ai-container tech-card">
      <!-- 头部 -->
      <div class="ai-header">
        <div class="ai-header__icon">✦</div>
        <div>
          <div style="font-weight: 600; font-size: 0.9375rem">AI 能耗优化助手</div>
          <div style="font-size: 0.75rem; color: var(--text-muted)">基于实时GPU数据的智能分析</div>
        </div>
      </div>

      <!-- 消息列表 -->
      <div class="ai-messages" ref="chatContainer">
        <div
          v-for="(msg, i) in messages"
          :key="i"
          class="msg"
          :class="msg.role === 'user' ? 'msg--user' : 'msg--bot'"
        >
          <div class="msg__avatar">{{ msg.role === 'user' ? '👤' : '✦' }}</div>
          <div class="msg__body">
            <div class="msg__content" v-html="msg.content.replace(/\n/g, '<br>')"></div>
            <div v-if="msg.suggestions?.length" class="msg__suggestions">
              <button
                v-for="(s, j) in msg.suggestions"
                :key="j"
                class="btn-tech"
                style="padding: 4px 10px; font-size: 0.6875rem"
                @click="useSuggestion(s)"
              >{{ s }}</button>
            </div>
          </div>
        </div>

        <div v-if="loading" class="msg msg--bot">
          <div class="msg__avatar">✦</div>
          <div class="msg__body">
            <div class="msg__content typing">
              <span></span><span></span><span></span>
            </div>
          </div>
        </div>
      </div>

      <!-- 输入框 -->
      <div class="ai-input">
        <textarea
          v-model="input"
          @keydown="handleKeydown"
          placeholder="输入问题，如：当前集群能耗情况如何？"
          rows="1"
        ></textarea>
        <button class="btn-tech btn-tech--primary" @click="sendMessage" :disabled="loading || !input.trim()">
          发送
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ai-page {
  max-width: 900px;
  margin: 0 auto;
  height: calc(100vh - 96px);
}

.ai-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 0;
}

.ai-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
}

.ai-header__icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: var(--gradient-blue);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  box-shadow: 0 0 12px rgba(56, 189, 248, 0.2);
}

.ai-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.msg {
  display: flex;
  gap: 10px;
  max-width: 85%;
}

.msg--user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.msg__avatar {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.875rem;
  flex-shrink: 0;
  background: rgba(255, 255, 255, 0.05);
}

.msg--bot .msg__avatar {
  background: var(--gradient-blue);
}

.msg__content {
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 0.8125rem;
  line-height: 1.7;
  color: var(--text-primary);
}

.msg--bot .msg__content {
  background: rgba(56, 189, 248, 0.06);
  border: 1px solid rgba(56, 189, 248, 0.1);
  border-radius: 4px 12px 12px 12px;
}

.msg--user .msg__content {
  background: var(--gradient-blue);
  color: white;
  border-radius: 12px 4px 12px 12px;
}

.msg__suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.typing span {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent-primary);
  margin: 0 2px;
  animation: typing-dot 1.4s ease-in-out infinite;
}
.typing span:nth-child(2) { animation-delay: 0.2s; }
.typing span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing-dot {
  0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
  40% { opacity: 1; transform: scale(1); }
}

.ai-input {
  display: flex;
  gap: 10px;
  padding: 16px 20px;
  border-top: 1px solid var(--border-color);
}

.ai-input textarea {
  flex: 1;
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid var(--border-color);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-primary);
  font-size: 0.875rem;
  resize: none;
  outline: none;
  font-family: inherit;
  transition: border-color 0.2s;
}

.ai-input textarea:focus {
  border-color: var(--accent-primary);
}
</style>

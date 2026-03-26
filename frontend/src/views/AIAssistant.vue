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
  <div class="ai-page ink-page-shell">
    <section class="ink-page-head tech-card">
      <div class="ink-page-head__body">
        <div class="ink-page-head__eyebrow">自然语言问答 · 实时状态理解 · 治理建议生成</div>
        <h2 class="ink-page-head__title">让运维判断，从冰冷面板变成可对话的墨卷</h2>
        <p class="ink-page-head__desc">
          你可以直接用自然语言询问当前功率、热点 GPU、调度建议或削峰思路。助手会结合平台当前采集到的真实状态给出解释性回答。
        </p>
      </div>
      <div class="ink-page-head__side">
        <div class="ink-page-head__quote">“言中有势，问中有策。”</div>
        <div class="ink-inline-meta">
          <span class="status-badge status-badge--ok">实时问答</span>
          <span class="status-badge status-badge--warning">面向治理场景</span>
        </div>
      </div>
    </section>

    <div class="ai-container tech-card">
      <div class="ai-header">
        <div class="ai-header__icon">智</div>
        <div>
          <div class="ai-header__title">AI 治理助手</div>
          <div class="ai-header__subtitle">基于实时 GPU 数据的智能分析与建议</div>
        </div>
        <div class="ai-header__seal ink-stamp">问</div>
      </div>

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
  max-width: 1200px;
  margin: 0 auto;
  min-height: calc(100vh - 220px);
}

.ai-container {
  display: flex;
  flex-direction: column;
  min-height: calc(100vh - 330px);
  padding: 0;
}

.ai-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 22px;
  border-bottom: 1px solid var(--border-color);
}

.ai-header__icon {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(46, 139, 87, 0.14), rgba(91, 140, 126, 0.22));
  border: 1px solid rgba(46, 139, 87, 0.14);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-seal);
  font-size: 1rem;
  color: var(--accent-primary);
}

.ai-header__title {
  font-family: var(--font-xingshu);
  font-size: 1.18rem;
  color: var(--text-primary);
}

.ai-header__subtitle {
  font-size: 0.78rem;
  color: var(--text-muted);
  margin-top: 4px;
}

.ai-header__seal {
  min-width: 38px;
  min-height: 38px;
}

.ai-messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px 22px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.msg {
  display: flex;
  gap: 12px;
  max-width: 85%;
}

.msg--user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.msg__avatar {
  width: 36px;
  height: 36px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-seal);
  font-size: 0.8rem;
  flex-shrink: 0;
  background: rgba(255, 255, 255, 0.5);
  border: 1px solid rgba(26, 26, 26, 0.06);
}

.msg--bot .msg__avatar {
  color: var(--accent-primary);
  background: rgba(46, 139, 87, 0.08);
}

.msg__content {
  padding: 14px 18px;
  border-radius: 22px;
  font-size: 0.84rem;
  line-height: 1.85;
  color: var(--text-primary);
}

.msg--bot .msg__content {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.82), rgba(248, 245, 240, 0.7));
  border: 1px solid rgba(58, 95, 75, 0.08);
  border-radius: 8px 22px 22px 22px;
}

.msg--user .msg__content {
  background: linear-gradient(135deg, #3A5F4B, #2E8B57);
  color: #fffdf9;
  border-radius: 22px 8px 22px 22px;
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
  padding: 18px 22px 22px;
  border-top: 1px solid var(--border-color);
}

.ai-input textarea {
  flex: 1;
  min-height: 50px;
  resize: none;
}

@media (max-width: 860px) {
  .ai-container {
    min-height: auto;
  }

  .ai-header,
  .ai-input {
    flex-direction: column;
    align-items: stretch;
  }

  .msg {
    max-width: 100%;
  }
}
</style>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import {
  aiChat,
  aiControlExecute,
  aiControlPlan,
  getLlmConfig,
  testLlmConfig,
  updateLlmConfig,
} from '../services/api'
import WorkspaceSummary from '../components/workspace/WorkspaceSummary.vue'
import WorkspaceTabs from '../components/workspace/WorkspaceTabs.vue'

const DEFAULT_INTRO = '你好，我是 AI 治理助手。我可以解释当前 GPU 状态，也可以在上方“AI 执行控制台”里把自然语言指令转换成可审核、可执行的治理动作。'
const BLOCKED_INTRO = 'AI 对话助手当前未启用。你可以继续使用上方的“AI 执行控制台”第一版，它支持规则解析；如果想获得更强的自然语言规划能力，请先在左侧接入 LLM。'
const QUICK_CONTROLS = [
  '把 GPU 0 的功耗上限调到 220W',
  '暂停 PID 1234',
  '恢复 PID 1234',
  '将 PID 1234 标记为可延迟',
  '把总功率预算设置为 1200W',
  '执行一次调度',
]
const activeTab = ref('control')
const assistantTabs = [
  { key: 'control', label: '执行控制', desc: '规划、执行' },
  { key: 'chat', label: '对话解释', desc: '问答与说明' },
  { key: 'model', label: '模型配置', desc: 'LLM 接入与测试' },
]

const messages = ref([{ role: 'assistant', content: DEFAULT_INTRO }])
const input = ref('')
const loading = ref(false)
const chatContainer = ref(null)

const llmReady = ref(false)
const llmBusy = ref(false)
const llmNotice = ref('')
const llmFeedback = ref(null)
const llmConfig = ref({
  enabled: false,
  base_url: 'https://api.deepseek.com/v1',
  model: 'deepseek-chat',
  has_api_key: false,
  api_key_masked: '',
  updated_at: null,
  source: 'default',
  llm_available: false,
})
const llmForm = ref({
  enabled: false,
  base_url: 'https://api.deepseek.com/v1',
  model: '',
  api_key: '',
  keep_existing_key: true,
})

const controlInput = ref('')
const controlPlanning = ref(false)
const controlExecuting = ref(false)
const controlPlan = ref(null)
const controlResult = ref(null)
const controlRiskAcknowledged = ref(false)

const llmSourceLabel = computed(() => {
  const source = llmConfig.value.source
  if (source === 'runtime') return '页面运行时'
  if (source === 'env') return '环境变量'
  return '默认值'
})
const hasStoredKey = computed(() => !!llmConfig.value.has_api_key)
const savedKeyHint = computed(() => {
  if (!hasStoredKey.value) return '当前未保存 API Key'
  return `已保存 Key：${llmConfig.value.api_key_masked || '******'}`
})
const canTestLlm = computed(() => {
  if (!llmForm.value.base_url.trim()) return false
  return !!llmForm.value.api_key.trim() || !!llmForm.value.keep_existing_key
})
const canSaveLlm = computed(() => {
  if (!llmForm.value.base_url.trim()) return false
  if (!llmForm.value.enabled) return true
  return !!llmForm.value.api_key.trim() || !!llmForm.value.keep_existing_key
})
const llmUpdatedAt = computed(() => {
  const ts = Number(llmConfig.value.updated_at || 0)
  if (!ts) return '未保存'
  return new Date(ts * 1000).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
})

const canPlanControl = computed(() => !!controlInput.value.trim())
const executableActions = computed(() =>
  (controlPlan.value?.actions || []).filter((item) => item.valid !== false)
)
const hasInvalidActions = computed(() =>
  (controlPlan.value?.actions || []).some((item) => item.valid === false)
)
const canExecuteControl = computed(() =>
  executableActions.value.length > 0
  && controlRiskAcknowledged.value
  && !controlExecuting.value
)
const controlPlannerLabel = computed(() =>
  controlPlan.value?.planner === 'llm' ? 'LLM 规划' : '规则解析'
)
const controlRiskLabel = computed(() => {
  const level = controlPlan.value?.risk_level || controlResult.value?.risk_level || 'low'
  if (level === 'high') return '高风险'
  if (level === 'medium') return '中风险'
  return '低风险'
})
const controlExecutionSummary = computed(() =>
  controlRiskAcknowledged.value
    ? '风险已确认，执行计划后会立即作用于真实设备、任务或预算配置。'
    : '未确认风险前，执行按钮保持禁用。'
)

const riskScopeGpuCount = computed(() => {
  const gpus = new Set()
  for (const a of executableActions.value) {
    if (a.target?.gpu_index !== undefined) gpus.add(a.target.gpu_index)
  }
  return gpus.size || (controlPlan.value?.context?.gpu_count || 0)
})
const riskScopeProcessCount = computed(() =>
  executableActions.value.filter(a => a.target?.pid).length
)
const riskActionTypes = computed(() => {
  const labels = { set_power_limit: '限功率', pause_task: '暂停', resume_task: '恢复', terminate_task: '终止', set_task_priority: '调级', configure_budget: '预算', run_schedule_once: '调度' }
  const types = [...new Set(executableActions.value.map(a => labels[a.action] || a.action))]
  return types.join(' · ') || '-'
})
const riskRollbackHint = computed(() => {
  const actions = executableActions.value.map(a => a.action)
  if (actions.includes('terminate_task')) return '终止操作不可回滚'
  if (actions.includes('pause_task')) return '暂停可通过恢复操作撤回'
  if (actions.includes('set_power_limit')) return '功耗限制可随时重新设置'
  return '可通过反向操作撤回'
})

function plannerClass(planner) {
  return planner === 'llm' ? 'status-badge--ok' : 'status-badge--warning'
}

function riskClass(level) {
  if (level === 'high') return 'status-badge--critical'
  if (level === 'medium') return 'status-badge--warning'
  return 'status-badge--ok'
}

function applyLlmSnapshot(snapshot) {
  const nextSnapshot = {
    enabled: !!snapshot?.enabled,
    base_url: snapshot?.base_url || 'https://api.deepseek.com/v1',
    model: snapshot?.model || '',
    has_api_key: !!snapshot?.has_api_key,
    api_key_masked: snapshot?.api_key_masked || '',
    updated_at: snapshot?.updated_at || null,
    source: snapshot?.source || 'default',
    llm_available: !!snapshot?.llm_available,
  }

  llmConfig.value = nextSnapshot
  llmForm.value = {
    enabled: nextSnapshot.enabled,
    base_url: nextSnapshot.base_url,
    model: nextSnapshot.has_api_key || nextSnapshot.enabled ? nextSnapshot.model : '',
    api_key: '',
    keep_existing_key: nextSnapshot.has_api_key,
  }
}

function resetMessages() {
  messages.value = [
    { role: 'assistant', content: llmReady.value ? DEFAULT_INTRO : BLOCKED_INTRO },
  ]
}

function syncLlmState(snapshot) {
  llmReady.value = !!snapshot?.llm_available
  if (llmReady.value) {
    llmNotice.value = ''
  } else if (!snapshot?.enabled) {
    llmNotice.value = 'AI 对话助手当前已关闭。执行控制台仍可使用规则解析模式。'
  } else if (!snapshot?.has_api_key) {
    llmNotice.value = '缺少 API Key。填写后先测试连接，再保存并生效。'
  } else {
    llmNotice.value = 'AI 对话助手尚未就绪，请先检查当前 LLM 配置。'
  }
  resetMessages()
}

function buildLlmPayload() {
  return {
    enabled: !!llmForm.value.enabled,
    base_url: llmForm.value.base_url.trim(),
    model: llmForm.value.model.trim(),
    api_key: llmForm.value.api_key.trim(),
    keep_existing_key: !!llmForm.value.keep_existing_key,
  }
}

async function loadAssistantCapability() {
  llmBusy.value = true
  try {
    const { data } = await getLlmConfig()
    applyLlmSnapshot(data)
    syncLlmState(data)
  } catch {
    llmReady.value = false
    llmNotice.value = '当前无法读取 AI 配置，请先检查后端服务是否正常。'
    resetMessages()
  } finally {
    llmBusy.value = false
  }
}

async function runLlmTest() {
  if (llmBusy.value || !canTestLlm.value) return

  llmBusy.value = true
  llmFeedback.value = null
  try {
    const { data } = await testLlmConfig(buildLlmPayload())
    if (!llmForm.value.model.trim() && data?.llm?.model) {
      llmForm.value.model = data.llm.model
    }
    llmFeedback.value = {
      type: 'success',
      text: `连接测试成功，当前模型：${data?.llm?.model || llmForm.value.model || '未识别'}`,
    }
  } catch (error) {
    llmFeedback.value = {
      type: 'error',
      text: error?.response?.data?.detail || 'LLM 连接测试失败，请检查地址、模型和密钥。',
    }
  } finally {
    llmBusy.value = false
  }
}

async function saveLlmConfig() {
  if (llmBusy.value || !canSaveLlm.value) return

  llmBusy.value = true
  llmFeedback.value = null
  try {
    const { data } = await updateLlmConfig(buildLlmPayload())
    applyLlmSnapshot(data?.llm || {})
    syncLlmState(data?.llm || {})
    llmFeedback.value = {
      type: 'success',
      text: data?.message || 'AI 助手配置已保存。',
    }
  } catch (error) {
    llmFeedback.value = {
      type: 'error',
      text: error?.response?.data?.detail || 'LLM 配置保存失败。',
    }
  } finally {
    llmBusy.value = false
  }
}

function useControlPrompt(text) {
  controlInput.value = text
  generateControlPlan()
}

async function generateControlPlan() {
  const message = controlInput.value.trim()
  if (!message || controlPlanning.value) return

  controlPlanning.value = true
  controlResult.value = null
  controlRiskAcknowledged.value = false
  try {
    const { data } = await aiControlPlan(message)
    controlPlan.value = data
  } catch (error) {
    controlPlan.value = null
    controlResult.value = {
      summary: error?.response?.data?.detail || '控制计划生成失败。',
      results: [],
      risk_level: 'high',
    }
  } finally {
    controlPlanning.value = false
  }
}

async function executeControlPlan() {
  if (!canExecuteControl.value) return

  controlExecuting.value = true
  try {
    const { data } = await aiControlExecute({
      message: controlInput.value.trim(),
      actions: executableActions.value.map((item) => ({
        action: item.action,
        target: item.target,
        reason: item.reason,
      })),
      acknowledge_risk: controlRiskAcknowledged.value,
    })
    controlResult.value = data
  } catch (error) {
    controlResult.value = {
      summary: error?.response?.data?.detail || '控制动作执行失败。',
      results: [],
      risk_level: 'high',
    }
  } finally {
    controlExecuting.value = false
  }
}

async function sendMessage() {
  const msg = input.value.trim()
  if (!msg || loading.value || !llmReady.value) return

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
  } catch {
    messages.value.push({
      role: 'assistant',
      content: 'AI 服务暂时不可用，请检查 LLM 配置。',
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

onMounted(() => {
  loadAssistantCapability()
})
</script>

<template>
  <div class="ai-page ink-page-shell">
    <WorkspaceSummary
      title="AI 执行控制台"
    >
      <template #meta>
        <div class="ink-inline-meta">
          <span class="status-badge status-badge--ok">可审核</span>
          <span class="status-badge status-badge--warning">需风险确认</span>
          <span class="status-badge" :class="llmReady ? 'status-badge--ok' : 'status-badge--warning'">
            {{ llmReady ? 'LLM 已就绪' : '规则解析模式' }}
          </span>
        </div>
      </template>
    </WorkspaceSummary>

    <div class="workspace-nav-layout">
      <div class="workspace-nav-layout__nav">
        <WorkspaceTabs
          v-model="activeTab"
          :items="assistantTabs"
        />
      </div>

      <section class="workspace-nav-layout__content">
    <aside v-if="activeTab === 'model'" class="ai-config tech-card">
        <div class="ai-config__head">
          <div>
            <div class="ai-config__eyebrow">在线接入 LLM</div>
            <div class="ai-config__title">让执行控制台从规则解析升级到自然语言规划</div>
          </div>
          <div class="ink-stamp ai-config__stamp">智</div>
        </div>

        <div class="ai-config__meta">
          <div class="ai-meta-card">
            <div class="ai-meta-card__label">当前状态</div>
            <div class="ai-meta-card__value">{{ llmReady ? '已启用' : '未启用' }}</div>
            <div class="ai-meta-card__desc">{{ llmReady ? '对话与规划均可增强' : '控制台将自动切到规则解析' }}</div>
          </div>
          <div class="ai-meta-card">
            <div class="ai-meta-card__label">配置来源</div>
            <div class="ai-meta-card__value">{{ llmSourceLabel }}</div>
            <div class="ai-meta-card__desc">最近保存：{{ llmUpdatedAt }}</div>
          </div>
        </div>

        <div v-if="!llmReady" class="ai-notice">
          <div class="ai-notice__title">LLM 未就绪</div>
          <div class="ai-notice__desc">{{ llmNotice }}</div>
        </div>

        <div class="ai-form">
          <label class="ai-form__field">
            <span class="ai-form__label">Base URL</span>
            <input
              v-model="llmForm.base_url"
              class="ai-form__input"
              type="text"
              placeholder="例如：https://api.deepseek.com/v1"
            />
          </label>

          <label class="ai-form__field">
            <span class="ai-form__label">Model</span>
            <input
              v-model="llmForm.model"
              class="ai-form__input"
              type="text"
              placeholder="可留空，测试时自动探测"
            />
          </label>

          <label class="ai-form__field">
            <span class="ai-form__label">API Key</span>
            <input
              v-model="llmForm.api_key"
              class="ai-form__input"
              type="password"
              :placeholder="hasStoredKey ? '留空则继续使用已保存 Key' : '输入 OpenAI 兼容接口密钥'"
            />
          </label>

          <div class="ai-form__hint">{{ savedKeyHint }}</div>

          <label v-if="hasStoredKey" class="ai-check">
            <input v-model="llmForm.keep_existing_key" type="checkbox" />
            <span>留空时继续使用已保存 Key</span>
          </label>

          <label class="ai-check">
            <input v-model="llmForm.enabled" type="checkbox" />
            <span>保存后立即启用 AI 助手</span>
          </label>

          <div class="ai-form__actions">
            <button class="btn-tech" :disabled="llmBusy || !canTestLlm" @click="runLlmTest">
              {{ llmBusy ? '处理中...' : '测试连接' }}
            </button>
            <button class="btn-tech btn-tech--primary" :disabled="llmBusy || !canSaveLlm" @click="saveLlmConfig">
              {{ llmBusy ? '处理中...' : '保存并生效' }}
            </button>
          </div>

          <div v-if="llmFeedback" class="ai-feedback" :class="`ai-feedback--${llmFeedback.type}`">
            {{ llmFeedback.text }}
          </div>

          <div class="ai-form__tip">
            执行控制台在未接入 LLM 时也能工作，但只会走规则解析。接入后，系统会基于当前真实 GPU/任务状态生成更像“运维助理”的动作计划。
          </div>
        </div>
    </aside>

    <section v-else-if="activeTab === 'control'" class="tech-card control-console">
          <div class="control-console__head">
            <div>
              <div class="control-console__eyebrow">AI 执行控制台</div>
              <div class="control-console__title">自然语言 -> 动作计划 -> 执行</div>
            </div>
            <div class="ink-inline-meta">
              <span class="status-badge" :class="plannerClass(controlPlan?.planner)">
                {{ controlPlan ? controlPlannerLabel : (llmReady ? 'LLM 待命' : '规则待命') }}
              </span>
              <span class="status-badge" :class="riskClass(controlPlan?.risk_level || 'low')">
                {{ controlRiskLabel }}
              </span>
            </div>
          </div>

          <div class="control-console__composer">
            <textarea
              v-model="controlInput"
              class="control-console__textarea"
              placeholder="例如：把 GPU 0 的功耗上限调到 220W；或者：暂停 PID 1234；或者：执行一次调度"
              rows="3"
            ></textarea>
            <div class="control-console__quick">
              <button
                v-for="item in QUICK_CONTROLS"
                :key="item"
                class="btn-tech"
                style="padding: 4px 10px; font-size: 0.72rem"
                @click="useControlPrompt(item)"
              >
                {{ item }}
              </button>
            </div>
          </div>

          <div class="control-console__mode">
            <label class="ai-check">
              <input v-model="controlRiskAcknowledged" type="checkbox" />
              <span>我已确认执行计划会直接改动真实设备、任务或预算</span>
            </label>
            <div class="control-console__hint">{{ controlExecutionSummary }}</div>
          </div>

          <div class="control-console__actions">
            <button class="btn-tech" :disabled="controlPlanning || !canPlanControl" @click="generateControlPlan">
              {{ controlPlanning ? '生成中...' : '生成执行计划' }}
            </button>
            <button
              class="btn-tech btn-tech--primary"
              :disabled="!canExecuteControl"
              @click="executeControlPlan"
            >
              {{ controlExecuting ? '执行中...' : '执行计划' }}
            </button>
          </div>

          <div v-if="controlPlan" class="control-plan">
            <div class="control-plan__summary">
              <div class="control-plan__title">计划概览</div>
              <div class="control-plan__desc">{{ controlPlan.summary }}</div>
              <div class="control-plan__meta">
                <span>规划器：{{ controlPlannerLabel }}</span>
                <span>动作数：{{ controlPlan.actions?.length || 0 }}</span>
                <span>可执行：{{ executableActions.length }}</span>
                <span>时段：{{ controlPlan.context?.time_period || '-' }}</span>
              </div>
            </div>

            <!-- 操作风险画像 -->
            <div v-if="executableActions.length" class="risk-profile">
              <div class="risk-profile__head">
                <span class="risk-profile__icon">鉴</span>
                <span class="risk-profile__title">操作风险画像</span>
              </div>
              <div class="risk-profile__grid">
                <div class="risk-profile__item">
                  <div class="risk-profile__label">影响范围</div>
                  <div class="risk-profile__value">
                    {{ riskScopeGpuCount }} 张 GPU · {{ riskScopeProcessCount }} 个进程
                  </div>
                </div>
                <div class="risk-profile__item">
                  <div class="risk-profile__label">动作类型</div>
                  <div class="risk-profile__value">{{ riskActionTypes }}</div>
                </div>
                <div class="risk-profile__item">
                  <div class="risk-profile__label">风险等级</div>
                  <div class="risk-profile__value" :class="`risk-profile__value--${controlPlan.risk_level || 'low'}`">
                    {{ controlRiskLabel }}
                  </div>
                </div>
                <div class="risk-profile__item">
                  <div class="risk-profile__label">回滚方式</div>
                  <div class="risk-profile__value">{{ riskRollbackHint }}</div>
                </div>
              </div>
            </div>

            <div v-if="controlPlan.warnings?.length" class="control-plan__warnings">
              <div
                v-for="(warning, index) in controlPlan.warnings"
                :key="index"
                class="control-plan__warning"
              >
                {{ warning }}
              </div>
            </div>

            <div class="control-plan__list">
              <div
                v-for="(item, index) in controlPlan.actions || []"
                :key="`${item.action}-${index}`"
                class="control-action"
                :class="{ 'control-action--invalid': item.valid === false }"
              >
                <div class="control-action__top">
                  <span class="control-action__index">动作 {{ index + 1 }}</span>
                  <span class="status-badge" :class="riskClass(item.risk_level || 'low')">
                    {{ item.action }}
                  </span>
                </div>
                <div class="control-action__label">{{ item.target_label || '-' }}</div>
                <div class="control-action__reason">{{ item.reason || '未提供动作原因。' }}</div>
                <div v-if="item.valid === false" class="control-action__blocked">
                  {{ item.blocked_reason || '当前动作不可执行' }}
                </div>
              </div>
            </div>
          </div>

          <div v-if="controlResult" class="control-result">
            <div class="control-result__head">
              <div class="control-plan__title">执行结果</div>
              <span class="status-badge" :class="riskClass(controlResult.risk_level || 'low')">
                执行结果
              </span>
            </div>
            <div class="control-result__summary">{{ controlResult.summary }}</div>
            <div class="control-result__list">
              <div
                v-for="(item, index) in controlResult.results || []"
                :key="`${item.action}-${index}`"
                class="control-result__item"
                :class="item.success ? 'control-result__item--ok' : 'control-result__item--fail'"
              >
                <div class="control-result__item-top">
                  <span>{{ item.label || item.action }}</span>
                  <span>{{ item.target_label || '-' }}</span>
                </div>
                <div v-if="item.error" class="control-result__error">{{ item.error }}</div>
                <div v-else class="control-result__message">
                  {{ item.message || (item.success ? '执行完成。' : '执行失败。') }}
                </div>
              </div>
            </div>
          </div>
    </section>

    <section v-else class="ai-container tech-card">
          <div class="ai-header">
            <div class="ai-header__icon">问</div>
            <div>
              <div class="ai-header__title">AI 问答助手</div>
              <div class="ai-header__subtitle">解释当前 GPU 状态、能耗与治理策略</div>
            </div>
            <div class="ai-header__seal ink-stamp">答</div>
          </div>

          <div ref="chatContainer" class="ai-messages">
            <div
              v-for="(msg, i) in messages"
              :key="i"
              class="msg"
              :class="msg.role === 'user' ? 'msg--user' : 'msg--bot'"
            >
              <div class="msg__avatar">{{ msg.role === 'user' ? '我' : '智' }}</div>
              <div class="msg__body">
                <div class="msg__content">{{ msg.content }}</div>
                <div v-if="msg.suggestions?.length" class="msg__suggestions">
                  <button
                    v-for="(s, j) in msg.suggestions"
                    :key="j"
                    class="btn-tech"
                    style="padding: 4px 10px; font-size: 0.6875rem"
                    @click="useSuggestion(s)"
                  >
                    {{ s }}
                  </button>
                </div>
              </div>
            </div>

            <div v-if="loading" class="msg msg--bot">
              <div class="msg__avatar">智</div>
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
              :placeholder="llmReady ? '输入问题，如：当前集群功耗为何偏高？' : '请先在左侧配置并启用 LLM 后再使用 AI 问答'"
              rows="1"
              :disabled="!llmReady"
            ></textarea>
            <button
              class="btn-tech btn-tech--primary"
              :disabled="loading || !input.trim() || !llmReady"
              @click="sendMessage"
            >
              发送
            </button>
          </div>
    </section>
      </section>
    </div>
  </div>
</template>

<style scoped>
.ai-page {
  max-width: 1280px;
  margin: 0 auto;
}

.ai-layout {
  display: grid;
  grid-template-columns: 360px minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}

.ai-main {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-width: 0;
}

.ai-config {
  padding: 20px 18px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.ai-config__head,
.control-console__head,
.control-console__mode,
.control-console__actions,
.control-plan__meta,
.control-result__head,
.ai-form__actions,
.ai-header,
.ai-input {
  display: flex;
  gap: 12px;
}

.ai-config__head,
.control-console__head,
.control-result__head,
.ai-header {
  align-items: center;
  justify-content: space-between;
}

.ai-config__eyebrow,
.control-console__eyebrow {
  font-size: 0.74rem;
  letter-spacing: 0.12em;
  color: var(--text-muted);
  text-transform: uppercase;
}

.ai-config__title,
.control-console__title {
  margin-top: 8px;
  font-family: var(--font-ui);
  font-size: 1.02rem;
  line-height: 1.55;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: var(--text-primary);
}

.ai-config__stamp {
  min-width: 40px;
  min-height: 40px;
}

.ai-config__meta {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.ai-meta-card,
.control-plan__summary,
.control-plan__warning,
.control-action,
.control-result__item {
  padding: 12px 14px;
  border-radius: 14px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-card);
  backdrop-filter: blur(12px) saturate(1.2);
  transition: transform 0.24s ease, background 0.24s ease, border-color 0.24s ease, box-shadow 0.24s ease;
}

.ai-meta-card:hover,
.control-action:hover,
.control-result__item:hover {
  transform: translateY(-1px);
  background: var(--bg-card-hover);
  border-color: var(--border-strong);
  box-shadow: var(--shadow-hover);
}

.ai-meta-card__label,
.ai-meta-card__desc,
.ai-form__hint,
.ai-form__tip,
.control-console__hint,
.control-plan__meta,
.control-action__reason,
.control-result__message,
.control-result__error {
  font-size: 0.74rem;
  color: var(--text-muted);
  line-height: 1.7;
}

.ai-meta-card__value {
  margin-top: 8px;
  font-size: 1rem;
  font-weight: 700;
  color: var(--text-primary);
}

.ai-notice {
  padding: 14px 18px;
  border-radius: 14px;
  border: 1px solid rgba(244, 185, 93, 0.22);
  background: rgba(244, 185, 93, 0.12);
  box-shadow: var(--shadow-card);
}

.ai-notice__title {
  font-size: 0.82rem;
  color: var(--accent-warning);
  font-weight: 700;
}

.ai-notice__desc {
  margin-top: 6px;
  font-size: 0.78rem;
  color: var(--text-secondary);
  line-height: 1.7;
}

.ai-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ai-form__field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ai-form__label {
  font-size: 0.78rem;
  color: var(--text-secondary);
}

.ai-form__actions {
  flex-wrap: wrap;
}

.ai-check {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 0.78rem;
  color: var(--text-secondary);
}

.ai-feedback {
  padding: 10px 12px;
  border-radius: 14px;
  font-size: 0.78rem;
  line-height: 1.7;
  border: 1px solid transparent;
}

.ai-feedback--success {
  background: linear-gradient(135deg, rgba(127, 142, 255, 0.16), rgba(110, 184, 255, 0.08));
  border-color: rgba(127, 142, 255, 0.24);
  color: var(--accent-primary);
}

.ai-feedback--error {
  background: rgba(255, 111, 150, 0.12);
  border-color: rgba(255, 111, 150, 0.22);
  color: var(--accent-danger);
}

.control-console,
.ai-container {
  padding: 20px 22px;
}

.control-console__composer {
  margin-top: 14px;
}

.control-console__textarea,
.ai-input textarea {
  width: 100%;
  min-height: 54px;
  resize: vertical;
  border-radius: 12px;
}

.control-console__quick,
.control-plan__warnings,
.control-plan__list,
.control-result__list,
.msg__suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.control-console__mode {
  margin-top: 14px;
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
}

.control-console__switch {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.control-console__hint {
  max-width: 420px;
}

.control-console__actions {
  margin-top: 14px;
  flex-wrap: wrap;
}

.control-plan,
.control-result {
  margin-top: 16px;
}

/* 操作风险画像 */
.risk-profile {
  margin-top: 12px;
  padding: 14px 16px;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(255, 111, 150, 0.1), rgba(244, 185, 93, 0.08), rgba(18, 26, 46, 0.88));
  border: 1px solid rgba(244, 185, 93, 0.22);
  box-shadow: var(--shadow-card);
}

.risk-profile__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.risk-profile__icon {
  width: 24px;
  height: 24px;
  border: 1.5px solid var(--accent-warning);
  border-radius: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-seal);
  font-size: 0.6rem;
  color: var(--accent-warning);
  opacity: 0.7;
  transform: rotate(-3deg);
}

.risk-profile__title {
  font-size: 0.82rem;
  font-weight: 700;
  color: var(--text-primary);
}

.risk-profile__grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.risk-profile__item {
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--border-color);
}

.risk-profile__label {
  font-size: 0.625rem;
  color: var(--text-muted);
  margin-bottom: 4px;
  letter-spacing: 0.08em;
}

.risk-profile__value {
  font-size: 0.82rem;
  color: var(--text-primary);
  font-weight: 600;
}

.risk-profile__value--low {
  color: var(--accent-primary);
}

.risk-profile__value--medium {
  color: var(--accent-warning);
}

.risk-profile__value--high {
  color: var(--accent-danger);
}

.control-plan__title {
  font-size: 0.92rem;
  font-weight: 700;
  color: var(--text-primary);
}

.control-plan__desc,
.control-result__summary,
.control-action__label {
  margin-top: 6px;
  font-size: 0.82rem;
  color: var(--text-secondary);
  line-height: 1.7;
}

.control-plan__meta {
  margin-top: 10px;
  flex-wrap: wrap;
}

.control-plan__warnings,
.control-plan__list,
.control-result__list {
  margin-top: 12px;
  flex-direction: column;
}

.control-plan__warning {
  border-color: rgba(244, 185, 93, 0.22);
  background: rgba(244, 185, 93, 0.12);
}

.control-action__top,
.control-result__item-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}

.control-action__index {
  font-size: 0.72rem;
  color: var(--text-muted);
}

.control-action__blocked {
  margin-top: 8px;
  font-size: 0.75rem;
  color: var(--accent-danger);
  line-height: 1.6;
}

.control-action--invalid {
  border-color: rgba(255, 111, 150, 0.22);
  background: rgba(255, 111, 150, 0.12);
}

.control-result__item--ok {
  border-color: rgba(127, 142, 255, 0.24);
  background: linear-gradient(180deg, rgba(127, 142, 255, 0.14), rgba(18, 26, 46, 0.82));
}

.control-result__item--fail {
  border-color: rgba(255, 111, 150, 0.22);
  background: linear-gradient(180deg, rgba(255, 111, 150, 0.12), rgba(18, 26, 46, 0.82));
}

.ai-container {
  display: flex;
  flex-direction: column;
  min-height: 520px;
}

.ai-header {
  padding-bottom: 14px;
  border-bottom: 1px solid var(--border-color);
}

.ai-header__icon {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(151, 165, 255, 0.92), rgba(110, 184, 255, 0.84));
  border: 1px solid rgba(127, 142, 255, 0.24);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-seal);
  font-size: 1rem;
  color: var(--text-primary);
  box-shadow: 0 14px 30px rgba(127, 142, 255, 0.22);
}

.ai-header__title {
  font-family: var(--font-ui);
  font-size: 1.08rem;
  color: var(--text-primary);
  font-weight: 600;
  letter-spacing: 0.02em;
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
  padding: 20px 0;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.msg {
  display: flex;
  gap: 12px;
  max-width: 88%;
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
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
}

.msg--bot .msg__avatar {
  color: var(--accent-primary);
  background: rgba(127, 142, 255, 0.14);
  border-color: rgba(127, 142, 255, 0.22);
}

.msg--user .msg__avatar {
  color: var(--text-primary);
  background: linear-gradient(135deg, rgba(151, 165, 255, 0.9), rgba(110, 184, 255, 0.78));
  border-color: transparent;
}

.msg__content {
  padding: 14px 18px;
  border-radius: 22px;
  font-size: 0.84rem;
  line-height: 1.85;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
}

.msg--bot .msg__content {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 8px 22px 22px 22px;
  box-shadow: var(--shadow-card);
}

.msg--user .msg__content {
  background: linear-gradient(135deg, rgba(127, 142, 255, 0.9), rgba(110, 184, 255, 0.78));
  color: var(--text-primary);
  border-radius: 22px 8px 22px 22px;
  box-shadow: 0 12px 28px rgba(127, 142, 255, 0.18);
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

.typing span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing-dot {
  0%, 80%, 100% {
    opacity: 0.3;
    transform: scale(0.8);
  }

  40% {
    opacity: 1;
    transform: scale(1);
  }
}

.ai-input {
  padding-top: 16px;
  border-top: 1px solid var(--border-color);
  align-items: flex-end;
}

.ai-form__tip {
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px dashed var(--border-color);
  background: rgba(255, 255, 255, 0.03);
}

@media (max-width: 1024px) {
  .ai-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 860px) {
  .ai-config__meta,
  .control-console__mode,
  .control-console__actions,
  .control-result__head,
  .ai-form__actions,
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

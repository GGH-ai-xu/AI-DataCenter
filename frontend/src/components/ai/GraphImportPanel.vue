<script setup>
import { computed } from 'vue'

import {
  getGraphConnectionStatus,
  getGraphExecuteDisabledReason,
  getGraphGenerateDisabledReason,
  getGraphRecoveryHint,
} from './graphStatus.js'

const props = defineProps({
  form: {
    type: Object,
    required: true,
  },
  summary: {
    type: Object,
    required: true,
  },
  draftResult: {
    type: Object,
    default: null,
  },
  feedback: {
    type: Object,
    default: null,
  },
  llmReady: {
    type: Boolean,
    default: false,
  },
  refreshBusy: {
    type: Boolean,
    default: false,
  },
  draftBusy: {
    type: Boolean,
    default: false,
  },
  executeBusy: {
    type: Boolean,
    default: false,
  },
  reconnectBusy: {
    type: Boolean,
    default: false,
  },
  demoBusy: {
    type: Boolean,
    default: false,
  },
  canGenerate: {
    type: Boolean,
    default: false,
  },
  canExecute: {
    type: Boolean,
    default: false,
  },
  busy: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['generate', 'execute', 'refresh', 'recover', 'reset', 'demo'])
const connectionStatus = computed(() => getGraphConnectionStatus(props.summary))
const actionBusy = computed(() =>
  props.refreshBusy || props.draftBusy || props.executeBusy || props.reconnectBusy || props.demoBusy
)
const canRecover = computed(() =>
  props.summary.local_start_available && !actionBusy.value
)
const canRequestGenerate = computed(() =>
  props.canGenerate && props.llmReady && !actionBusy.value
)
const canRequestExecute = computed(() =>
  props.canExecute && !actionBusy.value
)
const generateBlockedReason = computed(() => getGraphGenerateDisabledReason({
  form: props.form,
  llmReady: props.llmReady,
  busy: actionBusy.value,
}))
const executeBlockedReason = computed(() => getGraphExecuteDisabledReason({
  draftResult: props.draftResult,
  summary: props.summary,
  busy: actionBusy.value,
}))
const recoveryHint = computed(() => getGraphRecoveryHint(props.summary))
const recoverLabel = computed(() =>
  props.summary.neo4j_connected ? '重连 Neo4j' : '启动/重连 Neo4j'
)

const isOptimizationMode = computed(() => props.form.mode === 'optimization')
const panelTitle = computed(() => '知识入图工作台')
const primaryStatLabel = computed(() =>
  isOptimizationMode.value ? '知识条目' : '论文数量'
)
const primaryStatValue = computed(() =>
  isOptimizationMode.value ? (props.summary.node_count || 0) : (props.summary.paper_count || 0)
)
const titlePlaceholder = computed(() =>
  isOptimizationMode.value
    ? '例如：高峰限功调度策略 / 预算护栏模板 / 三层调度总则'
    : '例如：GraphRAG: Unlocking LLM Discovery on Narrative Private Data'
)
const abstractLabel = computed(() =>
  isOptimizationMode.value ? '规则概述' : '摘要'
)
const abstractPlaceholder = computed(() =>
  isOptimizationMode.value
    ? '先概括约束、适用时段、优化目标和核心动作。'
    : '粘贴摘要，供 AI 先抓住核心方法、任务、数据集和指标。'
)
const contentLabel = computed(() =>
  isOptimizationMode.value ? '规则正文 / 模板说明' : '正文片段'
)
const contentPlaceholder = computed(() =>
  isOptimizationMode.value
    ? '粘贴调度规则、能耗预算说明、代码模板说明或项目材料中的优化段落。'
    : '时间不够时，直接粘贴方法章节、实验章节或结论章节。'
)
const panelTip = computed(() =>
  isOptimizationMode.value
    ? '优化模式会把规则、约束、预算、策略、模板和接口收敛到统一图谱结构，适合后续做检索、问答和策略生成。'
    : '论文模式会把论文里的方法、任务、数据集和指标整理成统一图谱结构，不需要先手写 Cypher。'
)
const demoSwitchHint = computed(() =>
  props.summary.paper_count > 0
    ? '当前图库以论文图谱为主。可切到优化图谱，用于策略检索和代码生成。'
    : '当前图库以优化图谱为主。可切到论文图谱，用于查看研究关系。'
)
const modeOptions = [
  { value: 'paper', label: '论文图谱' },
  { value: 'optimization', label: '优化本体' },
]
const sourceTypeOptions = computed(() => (
  isOptimizationMode.value
    ? [
        { value: 'rule', label: '规则' },
        { value: 'strategy', label: '策略' },
        { value: 'template', label: '模板' },
        { value: 'api', label: '接口' },
      ]
    : [
        { value: 'paper', label: '论文' },
        { value: 'report', label: '报告' },
        { value: 'tech_note', label: '技术资料' },
      ]
))
</script>

<template>
  <section class="tech-card graph-panel">
    <div class="graph-panel__head">
      <div>
        <div class="graph-panel__eyebrow">知识入图</div>
        <div class="graph-panel__title">{{ panelTitle }}</div>
      </div>
      <div class="ink-inline-meta">
        <span class="status-badge" :class="props.summary.neo4j_connected ? 'status-badge--ok' : 'status-badge--warning'">
          {{ props.summary.neo4j_connected ? 'Neo4j 在线' : 'Neo4j 未连接' }}
        </span>
        <span class="status-badge">{{ connectionStatus }}</span>
      </div>
    </div>

    <div class="graph-panel__utility">
      <div>
        <div class="graph-panel__utility-title">当前入图模式</div>
        <div class="graph-panel__utility-desc">{{ panelTip }}</div>
      </div>
      <div class="graph-panel__utility-badges">
        <span class="status-badge">{{ primaryStatLabel }} {{ primaryStatValue }}</span>
        <span class="status-badge">{{ props.summary.node_count || 0 }} 节点</span>
        <span class="status-badge">{{ props.summary.relation_count || 0 }} 关系</span>
      </div>
    </div>

    <div class="graph-panel__meta-grid">
      <label class="graph-field">
        <span class="graph-field__label">图谱模式</span>
        <select v-model="props.form.mode" class="graph-field__input graph-field__input--select">
          <option v-for="option in modeOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
        </select>
      </label>

      <label class="graph-field">
        <span class="graph-field__label">来源类型</span>
        <select v-model="props.form.sourceType" class="graph-field__input graph-field__input--select">
          <option v-for="option in sourceTypeOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
        </select>
      </label>

      <label class="graph-field">
        <span class="graph-field__label">领域标签</span>
        <input
          v-model="props.form.domainTag"
          class="graph-field__input"
          type="text"
          :placeholder="isOptimizationMode ? '例如：智算中心优化 / 调度治理' : '例如：GraphRAG / RAG'"
        />
      </label>

      <label class="graph-field">
        <span class="graph-field__label">适用场景</span>
        <input
          v-model="props.form.scenario"
          class="graph-field__input"
          type="text"
          :placeholder="isOptimizationMode ? '例如：高峰限功 / 碳预算控制' : '例如：场景展示 / 文献综述'"
        />
      </label>
    </div>

    <div class="graph-panel__fields">
      <label class="graph-field">
        <span class="graph-field__label">标题</span>
        <input
          v-model="props.form.title"
          class="graph-field__input"
          type="text"
          :placeholder="titlePlaceholder"
        />
      </label>

      <label class="graph-field">
        <span class="graph-field__label">{{ abstractLabel }}</span>
        <textarea
          v-model="props.form.abstract"
          class="graph-field__input graph-field__input--textarea"
          rows="5"
          :placeholder="abstractPlaceholder"
        ></textarea>
      </label>

      <label class="graph-field">
        <span class="graph-field__label">{{ contentLabel }}</span>
        <textarea
          v-model="props.form.content"
          class="graph-field__input graph-field__input--textarea graph-field__input--large"
          rows="10"
          :placeholder="contentPlaceholder"
        ></textarea>
      </label>
    </div>

    <div v-if="props.feedback" class="graph-feedback" :class="`graph-feedback--${props.feedback.type}`">
      {{ props.feedback.text }}
    </div>

    <div class="graph-panel__status-strip">
      <div class="graph-panel__status-item">
        <span>草稿条件</span>
        <strong>{{ generateBlockedReason || '标题、内容与 LLM 已就绪，可生成图谱草稿。' }}</strong>
      </div>
      <div class="graph-panel__status-item">
        <span>写入条件</span>
        <strong>{{ executeBlockedReason || '草稿与 Neo4j 已就绪，可直接写入图库。' }}</strong>
      </div>
      <div class="graph-panel__status-item">
        <span>连接处理</span>
        <strong>{{ recoveryHint }}</strong>
      </div>
    </div>

    <div class="graph-panel__footer">
      <div class="graph-panel__footer-group">
        <button class="btn-tech" :disabled="actionBusy" @click="emit('refresh')">
          {{ props.refreshBusy ? '刷新中...' : '刷新图库状态' }}
        </button>
        <button
          class="btn-tech"
          :disabled="!canRecover"
          @click="emit('recover')"
        >
          {{ props.reconnectBusy ? '处理中...' : recoverLabel }}
        </button>
        <button v-if="props.busy" class="btn-tech" @click="emit('reset')">
          重置状态
        </button>
      </div>

      <div class="graph-panel__footer-group graph-panel__footer-group--primary">
        <div class="graph-panel__demo-text">{{ demoSwitchHint }}</div>
        <div class="graph-panel__footer-actions">
          <button class="btn-tech" :disabled="actionBusy" @click="emit('demo', 'paper')">
            {{ props.demoBusy ? '切换中...' : '切到论文图' }}
          </button>
          <button class="btn-tech" :disabled="actionBusy" @click="emit('demo', 'optimization')">
            {{ props.demoBusy ? '切换中...' : '切到优化图' }}
          </button>
          <button
            class="btn-tech"
            :disabled="!canRequestGenerate"
            @click="emit('generate')"
          >
            {{ props.draftBusy ? '生成中...' : '生成图谱草稿' }}
          </button>
          <button
            class="btn-tech btn-tech--primary"
            :disabled="!canRequestExecute"
            @click="emit('execute')"
          >
            {{ props.executeBusy ? '写入中...' : '写入 Neo4j' }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.graph-panel {
  padding: 20px 22px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.graph-panel__head,
.graph-panel__utility,
.graph-panel__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.graph-panel__eyebrow {
  font-size: 0.74rem;
  letter-spacing: 0.12em;
  color: var(--text-muted);
  text-transform: uppercase;
}

.graph-panel__title {
  margin-top: 8px;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.graph-panel__meta-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.graph-panel__utility {
  align-items: flex-start;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid var(--border-color);
  background: var(--bg-surface);
}

.graph-panel__utility-title {
  font-size: 0.76rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.graph-panel__utility-desc,
.graph-panel__demo-text {
  margin-top: 6px;
  font-size: 0.74rem;
  color: var(--text-muted);
  line-height: 1.7;
}

.graph-panel__utility-badges,
.graph-panel__footer-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.graph-panel__fields {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.graph-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.graph-field__label {
  font-size: 0.78rem;
  color: var(--text-secondary);
}

.graph-field__input {
  width: 100%;
  min-height: 44px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background: var(--field-background);
  color: var(--text-primary);
  outline: none;
  transition: border-color 0.2s ease, background 0.2s ease;
}

.graph-field__input:focus {
  border-color: var(--border-strong);
  background: var(--field-background-focus);
}

.graph-field__input--select {
  appearance: none;
}

.graph-field__input--textarea {
  resize: vertical;
}

.graph-field__input--large {
  min-height: 220px;
}

.graph-feedback {
  padding: 10px 12px;
  border-radius: 14px;
  font-size: 0.78rem;
  line-height: 1.7;
  border: 1px solid transparent;
}

.graph-feedback--success {
  background: var(--state-ok-bg);
  border-color: var(--state-ok-border);
  color: var(--state-ok-text);
}

.graph-feedback--error {
  background: var(--state-danger-bg);
  border-color: var(--state-danger-border);
  color: var(--state-danger-text);
}

.graph-panel__status-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.graph-panel__status-item {
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: var(--bg-surface);
}

.graph-panel__status-item span {
  display: block;
  font-size: 0.74rem;
  color: var(--text-muted);
}

.graph-panel__status-item strong {
  display: block;
  margin-top: 8px;
  font-size: 0.82rem;
  color: var(--text-primary);
  line-height: 1.65;
}

.graph-panel__footer {
  align-items: flex-start;
}

.graph-panel__footer-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.graph-panel__footer-group--primary {
  flex-direction: column;
  align-items: flex-end;
}

@media (max-width: 1200px) {
  .graph-panel__meta-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 960px) {
  .graph-panel__head,
  .graph-panel__utility,
  .graph-panel__footer,
  .graph-panel__footer-group--primary {
    flex-direction: column;
    align-items: flex-start;
  }

  .graph-panel__status-strip {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .graph-panel__meta-grid {
    grid-template-columns: 1fr;
  }
}
</style>

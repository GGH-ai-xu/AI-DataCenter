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

const emit = defineEmits(['generate', 'execute', 'refresh', 'recover', 'reset'])
const connectionStatus = computed(() => getGraphConnectionStatus(props.summary))
const actionBusy = computed(() =>
  props.refreshBusy || props.draftBusy || props.executeBusy || props.reconnectBusy
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
</script>

<template>
  <section class="tech-card graph-panel">
    <div class="graph-panel__head">
      <div>
        <div class="graph-panel__eyebrow">知识入图</div>
        <div class="graph-panel__title">论文文本 -> 图谱草稿 -> Neo4j</div>
      </div>
      <div class="ink-inline-meta">
        <span class="status-badge" :class="props.summary.neo4j_connected ? 'status-badge--ok' : 'status-badge--warning'">
          {{ props.summary.neo4j_connected ? 'Neo4j 在线' : 'Neo4j 未连接' }}
        </span>
        <span class="status-badge">{{ props.summary.database || 'neo4j' }}</span>
      </div>
    </div>

    <div class="graph-panel__stats">
      <div class="graph-panel__stat">
        <span>论文数量</span>
        <strong>{{ props.summary.paper_count || 0 }}</strong>
      </div>
      <div class="graph-panel__stat">
        <span>总节点数</span>
        <strong>{{ props.summary.node_count || 0 }}</strong>
      </div>
      <div class="graph-panel__stat">
        <span>图库关系</span>
        <strong>{{ props.summary.relation_count || 0 }}</strong>
      </div>
      <div class="graph-panel__stat">
        <span>连接状态</span>
        <strong>{{ connectionStatus }}</strong>
      </div>
    </div>

    <div class="graph-panel__fields">
      <label class="graph-field">
        <span class="graph-field__label">标题</span>
        <input
          v-model="props.form.title"
          class="graph-field__input"
          type="text"
          placeholder="例如：GraphRAG: Unlocking LLM Discovery on Narrative Private Data"
        />
      </label>

      <label class="graph-field">
        <span class="graph-field__label">摘要</span>
        <textarea
          v-model="props.form.abstract"
          class="graph-field__input graph-field__input--textarea"
          rows="5"
          placeholder="粘贴摘要，供 AI 先抓住核心方法、任务、数据集和指标。"
        ></textarea>
      </label>

      <label class="graph-field">
        <span class="graph-field__label">正文片段</span>
        <textarea
          v-model="props.form.content"
          class="graph-field__input graph-field__input--textarea graph-field__input--large"
          rows="10"
          placeholder="时间不够时，直接粘贴方法章节、实验章节或结论章节。"
        ></textarea>
      </label>
    </div>

    <div v-if="props.feedback" class="graph-feedback" :class="`graph-feedback--${props.feedback.type}`">
      {{ props.feedback.text }}
    </div>

    <div class="graph-panel__actions">
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
      <button
        class="btn-tech"
        :disabled="!canRequestGenerate"
        @click="emit('generate')"
      >
        {{ props.draftBusy ? '生成中...' : '生成 Cypher 草稿' }}
      </button>
      <button
        class="btn-tech btn-tech--primary"
        :disabled="!canRequestExecute"
        @click="emit('execute')"
      >
        {{ props.executeBusy ? '写入中...' : '写入 Neo4j' }}
      </button>
      <button v-if="props.busy" class="btn-tech" @click="emit('reset')">
        重置状态
      </button>
    </div>

    <div class="graph-panel__blockers">
      <div class="graph-panel__blocker">
        <span>草稿前置</span>
        <strong>{{ generateBlockedReason || '标题、内容与 LLM 已就绪，可生成图谱草稿。' }}</strong>
      </div>
      <div class="graph-panel__blocker">
        <span>写入前置</span>
        <strong>{{ executeBlockedReason || '草稿与 Neo4j 已就绪，可直接写入图库。' }}</strong>
      </div>
      <div class="graph-panel__blocker">
        <span>图库修复</span>
        <strong>{{ recoveryHint }}</strong>
      </div>
    </div>

    <div class="graph-panel__tip">
      第一版只支持固定 schema。你只需要提供论文内容，不需要先手动写 Cypher。
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
.graph-panel__actions {
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

.graph-panel__stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.graph-panel__stat {
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  box-shadow: var(--shadow-card);
}

.graph-panel__stat span,
.graph-panel__tip {
  font-size: 0.74rem;
  color: var(--text-muted);
  line-height: 1.7;
}

.graph-panel__stat strong {
  display: block;
  margin-top: 6px;
  font-size: 0.96rem;
  color: var(--text-primary);
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
  background: rgba(10, 16, 28, 0.88);
  color: var(--text-primary);
  outline: none;
  transition: border-color 0.2s ease, background 0.2s ease;
}

.graph-field__input:focus {
  border-color: var(--border-strong);
  background: rgba(12, 18, 31, 0.96);
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
  background: rgba(127, 142, 255, 0.14);
  border-color: rgba(127, 142, 255, 0.22);
  color: var(--accent-primary);
}

.graph-feedback--error {
  background: rgba(255, 111, 150, 0.12);
  border-color: rgba(255, 111, 150, 0.22);
  color: var(--accent-danger);
}

.graph-panel__actions {
  justify-content: flex-start;
  flex-wrap: wrap;
}

.graph-panel__blockers {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.graph-panel__blocker {
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: rgba(13, 21, 37, 0.9);
  box-shadow: var(--shadow-card);
}

.graph-panel__blocker span {
  font-size: 0.72rem;
  color: var(--text-muted);
}

.graph-panel__blocker strong {
  display: block;
  margin-top: 6px;
  font-size: 0.82rem;
  line-height: 1.7;
  color: var(--text-primary);
}

@media (max-width: 960px) {
  .graph-panel__stats {
    grid-template-columns: 1fr;
  }

  .graph-panel__blockers {
    grid-template-columns: 1fr;
  }
}
</style>

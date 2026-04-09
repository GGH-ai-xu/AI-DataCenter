<script setup>
import { computed } from 'vue'

const SAMPLE_QUESTIONS = [
  '这几篇论文之间的共同主线是什么？',
  'Self-RAG 和 GraphRAG 有什么关系？',
  '当前图谱里覆盖了哪些任务和数据集？',
  '为什么说某个方法是当前图里的核心节点？',
]

const props = defineProps({
  summary: {
    type: Object,
    required: true,
  },
  form: {
    type: Object,
    required: true,
  },
  result: {
    type: Object,
    required: true,
  },
  busy: {
    type: Boolean,
    default: false,
  },
  canAsk: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['ask'])

const confidenceLabel = computed(() => {
  const level = String(props.result.confidence || 'low').toLowerCase()
  if (level === 'high') return '高'
  if (level === 'medium') return '中'
  return '低'
})

const answerModeLabel = computed(() =>
  props.result.used_llm ? '图谱证据 + LLM 归纳' : '图谱证据直答'
)

const questionScopeLabel = computed(() => {
  const paperCount = Number(props.result.paper_titles?.length || 0)
  if (!paperCount) return '当前未命中明确论文'
  return `已命中 ${paperCount} 篇相关论文`
})

function submitQuestion(question = '') {
  const normalizedQuestion = String(question || props.form.question || '').trim()
  if (!normalizedQuestion) return
  props.form.question = normalizedQuestion
  emit('ask', normalizedQuestion)
}
</script>

<template>
  <section class="graph-qa tech-card">
    <div class="graph-qa__head">
      <div>
        <div class="graph-qa__eyebrow">图谱问答</div>
        <div class="graph-qa__title">图谱问答台</div>
        <div class="graph-qa__subtitle">
          先从图谱里取证，再生成回答和追问，适合直接回答“结论是什么、依据是什么”。
        </div>
      </div>
      <div class="ink-inline-meta">
        <span class="status-badge" :class="props.summary.neo4j_connected ? 'status-badge--ok' : 'status-badge--warning'">
          {{ props.summary.neo4j_connected ? '图库在线' : '图库离线' }}
        </span>
        <span class="status-badge">
          {{ answerModeLabel }}
        </span>
      </div>
    </div>

    <div class="graph-qa__composer">
      <label class="graph-qa__field">
        <span>问题</span>
        <textarea
          v-model="props.form.question"
          rows="3"
          placeholder="例如：这几篇论文之间的共同主线是什么？"
        ></textarea>
      </label>
      <div class="graph-qa__actions">
        <button
          class="btn-tech btn-tech--primary"
          :disabled="!props.canAsk"
          @click="submitQuestion()"
        >
          {{ props.busy ? '分析中...' : '生成回答' }}
        </button>
      </div>
    </div>

    <div class="graph-qa__samples">
      <span class="graph-qa__samples-label">快捷问题</span>
      <button
        v-for="question in SAMPLE_QUESTIONS"
        :key="question"
        class="graph-qa__sample"
        @click="submitQuestion(question)"
      >
        {{ question }}
      </button>
    </div>

    <div class="graph-qa__stats">
      <div class="graph-qa__stat">
        <span>命中节点</span>
        <strong>{{ props.result.matched_node_count || 0 }}</strong>
      </div>
      <div class="graph-qa__stat">
        <span>命中关系</span>
        <strong>{{ props.result.matched_relationship_count || 0 }}</strong>
      </div>
      <div class="graph-qa__stat">
        <span>回答可信度</span>
        <strong>{{ confidenceLabel }}</strong>
      </div>
      <div class="graph-qa__stat">
        <span>覆盖论文</span>
        <strong>{{ props.result.paper_titles?.length || 0 }}</strong>
      </div>
    </div>

    <div class="graph-qa__summary-bar">
      <div class="graph-qa__summary-item">
        <span>问答方式</span>
        <strong>{{ answerModeLabel }}</strong>
      </div>
      <div class="graph-qa__summary-item">
        <span>命中范围</span>
        <strong>{{ questionScopeLabel }}</strong>
      </div>
      <div class="graph-qa__summary-item">
        <span>使用建议</span>
        <strong>先看摘要，再展开证据节点和证据关系。</strong>
      </div>
    </div>

    <div v-if="!props.result.summary && !props.busy" class="graph-qa__empty">
      这里会把结果整理成“摘要 + 证据 + 后续问题”的形式，方便直接展示依据。
    </div>

    <template v-else>
      <div class="graph-qa__answer">
        <div class="graph-qa__answer-card graph-qa__answer-card--summary">
          <div class="graph-qa__answer-label">回答摘要</div>
          <div class="graph-qa__answer-value">{{ props.result.summary || '正在整理图谱回答...' }}</div>
        </div>
        <div class="graph-qa__answer-card">
          <div class="graph-qa__answer-label">详细回答</div>
          <div class="graph-qa__answer-body">{{ props.result.answer || '正在等待图谱回答返回。' }}</div>
        </div>
      </div>

      <div class="graph-qa__evidence-grid">
        <article class="graph-qa__panel">
          <div class="graph-qa__panel-head">证据摘要</div>
          <div v-if="props.result.evidence?.length" class="graph-qa__list">
            <div
              v-for="(item, index) in props.result.evidence"
              :key="`${index}-${item}`"
              class="graph-qa__list-item"
            >
              {{ item }}
            </div>
          </div>
          <div v-else class="graph-qa__panel-empty">
            当前还没有返回可展示的证据摘要。
          </div>
        </article>

        <article class="graph-qa__panel">
          <div class="graph-qa__panel-head">证据节点</div>
          <div v-if="props.result.evidence_nodes?.length" class="graph-qa__node-list">
            <div
              v-for="node in props.result.evidence_nodes"
              :key="node.id"
              class="graph-qa__node"
            >
              <div class="graph-qa__node-top">
                <span class="status-badge status-badge--ok">{{ node.label }}</span>
                <span class="graph-qa__node-name">{{ node.name }}</span>
              </div>
              <div v-if="node.paper_title" class="graph-qa__node-meta">所属主题：{{ node.paper_title }}</div>
              <div v-if="node.description" class="graph-qa__node-desc">{{ node.description }}</div>
            </div>
          </div>
          <div v-else class="graph-qa__panel-empty">
            当前问题还没有命中明确的证据节点。
          </div>
        </article>
      </div>

      <article class="graph-qa__panel">
        <div class="graph-qa__panel-head">证据关系</div>
        <div v-if="props.result.evidence_relationships?.length" class="graph-qa__relation-list">
          <div
            v-for="relationship in props.result.evidence_relationships"
            :key="relationship.id"
            class="graph-qa__relation"
          >
            <span class="graph-qa__relation-type">{{ relationship.type }}</span>
            <span class="graph-qa__relation-main">{{ relationship.source_name || relationship.source_id }} -> {{ relationship.target_name || relationship.target_id }}</span>
            <span v-if="relationship.description" class="graph-qa__relation-desc">{{ relationship.description }}</span>
          </div>
        </div>
        <div v-else class="graph-qa__panel-empty">
          当前问题还没有命中可直接展示的证据关系。
        </div>
      </article>

      <article v-if="props.result.follow_ups?.length" class="graph-qa__panel">
        <div class="graph-qa__panel-head">后续问题</div>
        <div class="graph-qa__follow-ups">
          <button
            v-for="question in props.result.follow_ups"
            :key="question"
            class="graph-qa__sample"
            @click="submitQuestion(question)"
          >
            {{ question }}
          </button>
        </div>
      </article>
    </template>
  </section>
</template>

<style scoped>
.graph-qa {
  padding: 22px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.graph-qa__head,
.graph-qa__actions,
.graph-qa__node-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.graph-qa__eyebrow {
  font-size: 0.72rem;
  letter-spacing: 0.16em;
  color: var(--text-muted);
  text-transform: uppercase;
}

.graph-qa__title {
  margin-top: 8px;
  font-size: 1.16rem;
  color: var(--text-primary);
  font-weight: 700;
}

.graph-qa__subtitle {
  margin-top: 8px;
  max-width: 860px;
  font-size: 0.8rem;
  line-height: 1.8;
  color: var(--text-secondary);
}

.graph-qa__composer,
.graph-qa__panel,
.graph-qa__answer-card,
.graph-qa__stat {
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  box-shadow: var(--shadow-card);
}

.graph-qa__field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.graph-qa__field span,
.graph-qa__samples-label,
.graph-qa__answer-label,
.graph-qa__panel-head,
.graph-qa__stat span {
  font-size: 0.76rem;
  color: var(--text-muted);
}

.graph-qa__field textarea {
  min-height: 88px;
  resize: vertical;
}

.graph-qa__actions {
  margin-top: 14px;
  justify-content: flex-start;
}

.graph-qa__samples,
.graph-qa__follow-ups {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.graph-qa__sample {
  padding: 8px 12px;
  border-radius: 999px;
  border: 1px solid var(--border-color);
  background: var(--bg-surface);
  color: var(--text-secondary);
  cursor: pointer;
  transition: transform 0.2s ease, border-color 0.2s ease, background 0.2s ease;
}

.graph-qa__sample:hover {
  transform: translateY(-1px);
  border-color: var(--border-strong);
  background: var(--bg-card-hover);
}

.graph-qa__stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.graph-qa__summary-bar {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.graph-qa__summary-item {
  padding: 12px 14px;
  border-radius: 16px;
  border: 1px solid var(--border-color);
  background: var(--bg-surface);
}

.graph-qa__summary-item span {
  font-size: 0.72rem;
  color: var(--text-muted);
}

.graph-qa__summary-item strong {
  display: block;
  margin-top: 8px;
  font-size: 0.8rem;
  line-height: 1.8;
  color: var(--text-primary);
}

.graph-qa__stat strong,
.graph-qa__answer-value {
  display: block;
  margin-top: 8px;
  font-size: 0.98rem;
  color: var(--text-primary);
  font-weight: 700;
}

.graph-qa__empty,
.graph-qa__panel-empty,
.graph-qa__list-item,
.graph-qa__node,
.graph-qa__relation {
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: var(--bg-surface);
  color: var(--text-secondary);
  line-height: 1.8;
}

.graph-qa__answer {
  display: grid;
  grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr);
  gap: 10px;
}

.graph-qa__answer-card--summary {
  background: var(--state-ok-bg);
  border-color: var(--state-ok-border);
}

.graph-qa__answer-body {
  margin-top: 10px;
  font-size: 0.82rem;
  line-height: 1.85;
  color: var(--text-primary);
}

.graph-qa__evidence-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.graph-qa__list,
.graph-qa__node-list,
.graph-qa__relation-list {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.graph-qa__node-name {
  color: var(--text-primary);
  font-weight: 600;
}

.graph-qa__node-meta,
.graph-qa__node-desc,
.graph-qa__relation-desc {
  margin-top: 6px;
  font-size: 0.74rem;
  line-height: 1.7;
  color: var(--text-secondary);
}

.graph-qa__relation-type {
  display: inline-flex;
  min-width: 72px;
  color: var(--text-primary);
  font-weight: 700;
}

.graph-qa__relation-main {
  color: var(--text-primary);
  font-weight: 600;
}

@media (max-width: 1100px) {
  .graph-qa__stats,
  .graph-qa__summary-bar,
  .graph-qa__answer,
  .graph-qa__evidence-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 860px) {
  .graph-qa {
    padding: 18px;
  }

  .graph-qa__head {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>

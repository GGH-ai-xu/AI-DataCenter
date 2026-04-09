<script setup>
import { computed } from 'vue'

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
    default: null,
  },
  busy: {
    type: Boolean,
    default: false,
  },
  canGenerate: {
    type: Boolean,
    default: false,
  },
  llmReady: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['generate', 'use-control', 'use-control-plan', 'ask'])

const SAMPLE_PROMPTS = [
  '高峰期降低总功耗，但不影响紧急任务',
  '预算吃紧时，给我一版保守调度策略和代码模板',
  '生成一段限功但保护 SLA 的调度代码模板',
]

const graphReady = computed(() => !!props.summary.neo4j_connected)
const statusText = computed(() => {
  if (!graphReady.value) return props.summary.message || 'Neo4j 未连接'
  if (props.result?.used_llm) return '图谱证据 + LLM 归纳'
  if (props.result) return '图谱证据 + 规则模板'
  return props.llmReady ? '图谱待检索' : '图谱待检索 / 无 LLM'
})
const blockedReason = computed(() => {
  if (!graphReady.value) return 'Neo4j 未连接，暂时无法从图里检索策略依据。'
  if (!String(props.form.message || '').trim()) return '请先输入优化目标。'
  return ''
})
const focusChips = computed(() => {
  const focus = props.result?.focus || {}
  return [
    ...(focus.strategies || []).map((item) => `策略 · ${item}`),
    ...(focus.constraints || []).map((item) => `约束 · ${item}`),
    ...(focus.templates || []).map((item) => `模板 · ${item}`),
    ...(focus.apis || []).map((item) => `接口 · ${item}`),
  ].slice(0, 8)
})
</script>

<template>
  <section class="tech-card strategy-panel">
    <div class="strategy-panel__head">
      <div>
        <div class="strategy-panel__eyebrow">策略生成</div>
        <div class="strategy-panel__title">策略生成台</div>
        <div class="strategy-panel__subtitle">
          基于当前图谱生成治理步骤、执行指令和代码模板，减少凭空编排。
        </div>
      </div>
      <div class="ink-inline-meta">
        <span class="status-badge" :class="graphReady ? 'status-badge--ok' : 'status-badge--warning'">
          {{ graphReady ? '图库在线' : '图库离线' }}
        </span>
        <span class="status-badge" :class="props.llmReady ? 'status-badge--ok' : 'status-badge--warning'">
          {{ statusText }}
        </span>
      </div>
    </div>

    <div class="strategy-panel__composer">
      <textarea
        v-model="props.form.message"
        class="strategy-panel__textarea"
        rows="4"
        placeholder="例如：高峰期降低总功耗，但不影响紧急任务，并生成一段可执行的调度代码模板"
      ></textarea>
      <div class="strategy-panel__samples">
        <button
          v-for="item in SAMPLE_PROMPTS"
          :key="item"
          class="btn-tech"
          @click="props.form.message = item"
        >
          {{ item }}
        </button>
      </div>
      <div class="strategy-panel__actions">
        <button
          class="btn-tech btn-tech--primary"
          :disabled="props.busy || !props.canGenerate"
          @click="emit('generate')"
        >
          {{ props.busy ? '生成中...' : '生成策略方案' }}
        </button>
        <div class="strategy-panel__hint">
          {{ blockedReason || '会优先使用图谱里的策略、约束、模板和接口名，尽量避免“瞎编代码”。' }}
        </div>
      </div>
    </div>

    <div v-if="props.result" class="strategy-panel__body">
      <div class="strategy-panel__overview">
        <div class="strategy-panel__summary">
          <div class="strategy-panel__section-label">策略摘要</div>
          <div class="strategy-panel__summary-value">{{ props.result.summary || '正在整理策略总结...' }}</div>
          <div class="strategy-panel__meta">
            <span>证据节点 {{ props.result.matched_node_count || 0 }}</span>
            <span>证据关系 {{ props.result.matched_relationship_count || 0 }}</span>
            <span>{{ props.result.used_llm ? 'LLM 已参与' : '规则模板回退' }}</span>
          </div>
        </div>

        <div class="strategy-panel__runtime">
          <div class="strategy-panel__section-label">运行态上下文</div>
          <pre class="strategy-panel__runtime-pre">{{ props.result.runtime_summary || '暂无运行态摘要。' }}</pre>
        </div>
      </div>

      <div v-if="focusChips.length" class="strategy-panel__chips">
        <span
          v-for="item in focusChips"
          :key="item"
          class="graph-catalog__chip"
        >
          {{ item }}
        </span>
      </div>

      <div class="strategy-panel__grid">
        <article class="strategy-card">
          <div class="strategy-panel__section-label">建议步骤</div>
          <div class="strategy-steps">
            <div
              v-for="(step, index) in props.result.strategy_steps || []"
              :key="`${index}-${step}`"
              class="strategy-step"
            >
              <span class="strategy-step__index">{{ index + 1 }}</span>
              <span>{{ step }}</span>
            </div>
          </div>
          <div class="strategy-card__risk">
            <strong>风险提示</strong>
            <span>{{ props.result.risk_notice || '执行前仍需人工核对目标 GPU、任务和预算。' }}</span>
          </div>
        </article>

        <article class="strategy-card">
          <div class="strategy-panel__section-label">执行指令</div>
          <div class="strategy-card__prompt">{{ props.result.control_prompt || '当前未生成控制台指令。' }}</div>
          <div class="strategy-card__prompt-actions">
            <button
              class="btn-tech"
              :disabled="!props.result.control_prompt"
              @click="emit('use-control', props.result.control_prompt)"
            >
              填入执行控制台
            </button>
            <button
              class="btn-tech btn-tech--primary"
              :disabled="!props.result.control_prompt"
              @click="emit('use-control-plan', props.result.control_prompt)"
            >
              直接生成执行计划
            </button>
          </div>
        </article>
      </div>

      <article class="strategy-card">
        <div class="strategy-panel__section-label">代码模板</div>
        <div class="strategy-card__code-head">
          <strong>{{ props.result.code_title || '未命名模板' }}</strong>
          <span class="status-badge">{{ props.result.code_language || 'python' }}</span>
        </div>
        <pre class="strategy-card__code"><code>{{ props.result.code_snippet || '# 当前未生成代码模板' }}</code></pre>
      </article>

      <div class="strategy-panel__grid">
        <article class="strategy-card">
          <div class="strategy-panel__section-label">图谱依据</div>
          <div class="strategy-evidence">
            <div
              v-for="(item, index) in props.result.evidence || []"
              :key="`${index}-${item}`"
              class="strategy-evidence__item"
            >
              {{ item }}
            </div>
          </div>
        </article>

        <article class="strategy-card">
          <div class="strategy-panel__section-label">后续问题</div>
          <div class="strategy-followups">
            <button
              v-for="item in props.result.follow_ups || []"
              :key="item"
              class="btn-tech"
              @click="emit('ask', item)"
            >
              {{ item }}
            </button>
          </div>
        </article>
      </div>
    </div>
  </section>
</template>

<style scoped>
.strategy-panel {
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.strategy-panel__head,
.strategy-panel__actions,
.strategy-card__code-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.strategy-panel__eyebrow {
  font-size: 0.72rem;
  letter-spacing: 0.14em;
  color: var(--text-muted);
  text-transform: uppercase;
}

.strategy-panel__title {
  margin-top: 8px;
  font-size: 1.04rem;
  font-weight: 600;
  color: var(--text-primary);
}

.strategy-panel__subtitle {
  margin-top: 8px;
  font-size: 0.8rem;
  line-height: 1.7;
  color: var(--text-secondary);
}

.strategy-panel__composer,
.strategy-card,
.strategy-panel__summary,
.strategy-panel__runtime {
  border-radius: 16px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  box-shadow: var(--shadow-card);
}

.strategy-panel__composer,
.strategy-card,
.strategy-panel__summary,
.strategy-panel__runtime {
  padding: 16px;
}

.strategy-panel__textarea {
  width: 100%;
  min-height: 120px;
  resize: vertical;
  border: 1px solid var(--border-color);
  border-radius: 14px;
  padding: 14px;
  background: var(--field-background);
  color: var(--text-primary);
  outline: none;
}

.strategy-panel__textarea:focus {
  border-color: var(--border-strong);
  background: var(--field-background-focus);
}

.strategy-panel__samples,
.strategy-panel__chips,
.strategy-followups {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.strategy-panel__hint,
.strategy-card__risk span,
.strategy-panel__meta,
.strategy-panel__runtime-pre,
.strategy-evidence__item {
  font-size: 0.76rem;
  line-height: 1.7;
  color: var(--text-secondary);
}

.graph-catalog__chip {
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid var(--border-color);
  background: var(--bg-surface);
  font-size: 0.72rem;
  color: var(--text-secondary);
}

.strategy-panel__actions {
  margin-top: 14px;
  align-items: flex-start;
}

.strategy-panel__body,
.strategy-panel__overview {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.strategy-panel__overview {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.strategy-panel__section-label {
  font-size: 0.74rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.strategy-panel__summary-value {
  margin-top: 8px;
  font-size: 0.94rem;
  line-height: 1.8;
  color: var(--text-primary);
}

.strategy-panel__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 10px;
}

.strategy-panel__runtime-pre,
.strategy-card__code {
  margin: 10px 0 0;
  white-space: pre-wrap;
  overflow-x: auto;
}

.strategy-panel__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.strategy-steps,
.strategy-evidence {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 10px;
}

.strategy-step,
.strategy-evidence__item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.strategy-step__index {
  width: 22px;
  height: 22px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--state-ok-bg);
  color: var(--accent-primary);
  font-size: 0.72rem;
  flex: none;
}

.strategy-card__risk,
.strategy-card__prompt {
  margin-top: 12px;
}

.strategy-card__prompt-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 12px;
}

.strategy-card__risk {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.strategy-card__prompt {
  font-size: 0.86rem;
  line-height: 1.75;
  color: var(--text-primary);
}

@media (max-width: 960px) {
  .strategy-panel__overview,
  .strategy-panel__grid {
    grid-template-columns: 1fr;
  }

  .strategy-panel__actions,
  .strategy-panel__head,
  .strategy-card__code-head {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>

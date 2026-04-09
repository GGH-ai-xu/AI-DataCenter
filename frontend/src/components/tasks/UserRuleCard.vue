<script setup>
import { ref, watch } from 'vue'

const ROLE_OPTIONS = Object.freeze({
  protected: '保护用户',
  member: '普通用户',
  restricted: '受限用户',
})

const props = defineProps({
  user: { type: Object, required: true },
})

const emit = defineEmits(['save', 'reset'])
const expanded = ref(false)
const draft = ref(buildRuleDraft(props.user))

watch(() => props.user, (user) => {
  draft.value = buildRuleDraft(user)
}, { deep: true })

function buildRuleDraft(user = {}) {
  const rule = user.governance_rule || {}
  return {
    role: rule.role || 'member',
    max_tasks: rule.max_tasks ?? 4,
    max_gpu_count: rule.max_gpu_count ?? 1,
    max_memory_gb: rule.max_memory_gb ?? 8,
    allow_preempt: rule.allow_preempt ?? true,
    note: rule.note || '',
  }
}

function workloadSummary(user = {}) {
  return user.workloadSummary || `${user.task_count || 0} 个任务 · ${user.gpu_count || 0} 张GPU`
}

function violationLabel(user = {}) {
  if (user.violationLabel) return user.violationLabel
  const violationCount = Number(user.violation_count || 0)
  return violationCount > 0 ? `违规 ${violationCount}` : '规则内'
}

function saveRule() {
  emit('save', {
    username: props.user.username,
    role: draft.value.role,
    max_tasks: Number(draft.value.max_tasks),
    max_gpu_count: Number(draft.value.max_gpu_count),
    max_memory_gb: Number(draft.value.max_memory_gb),
    allow_preempt: Boolean(draft.value.allow_preempt),
    note: draft.value.note || '',
  })
}
</script>

<template>
  <article class="rule-card">
    <div class="rule-card__top">
      <div>
        <div class="rule-card__name">{{ props.user.username }}</div>
        <div class="rule-card__meta">{{ workloadSummary(props.user) }}</div>
      </div>
      <span class="rule-card__status" :class="props.user.violation_count ? 'rule-card__status--warn' : 'rule-card__status--ok'">
        {{ violationLabel(props.user) }}
      </span>
    </div>

    <div class="rule-card__summary">
      <span>角色 {{ ROLE_OPTIONS[draft.role] }}</span>
      <span>任务 {{ draft.max_tasks }}</span>
      <span>GPU {{ draft.max_gpu_count }}</span>
      <span>显存 {{ draft.max_memory_gb }} GB</span>
    </div>

    <div class="rule-card__actions">
      <button type="button" class="action-card" @click="expanded = !expanded">
        <span class="action-card__icon">✎</span>
        <span class="action-card__body">
          <strong>{{ expanded ? '收起规则' : '编辑规则' }}</strong>
          <small>展开当前用户的治理额度与让路策略。</small>
        </span>
      </button>

      <button type="button" class="action-card action-card--primary" @click="saveRule">
        <span class="action-card__icon">✓</span>
        <span class="action-card__body">
          <strong>保存规则</strong>
          <small>立即写入当前卡片里的用户治理规则。</small>
        </span>
      </button>

      <button type="button" class="action-card" :disabled="!props.user.hasStoredRule" @click="emit('reset', props.user.username)">
        <span class="action-card__icon">↺</span>
        <span class="action-card__body">
          <strong>恢复默认</strong>
          <small>删除已存规则，回到系统默认额度。</small>
        </span>
      </button>
    </div>

    <div v-if="expanded" class="rule-card__form">
      <select v-model="draft.role" class="rule-field">
        <option value="protected">{{ ROLE_OPTIONS.protected }}</option>
        <option value="member">{{ ROLE_OPTIONS.member }}</option>
        <option value="restricted">{{ ROLE_OPTIONS.restricted }}</option>
      </select>
      <input v-model.number="draft.max_tasks" class="rule-field" type="number" min="1" max="64" placeholder="最多任务" />
      <input v-model.number="draft.max_gpu_count" class="rule-field" type="number" min="1" max="16" placeholder="最多 GPU" />
      <input v-model.number="draft.max_memory_gb" class="rule-field" type="number" min="1" step="0.5" max="1024" placeholder="显存额度(GB)" />
      <select v-model="draft.allow_preempt" class="rule-field">
        <option :value="true">允许让路</option>
        <option :value="false">保护任务</option>
      </select>
      <input v-model="draft.note" class="rule-field rule-field--wide" type="text" placeholder="备注" />
    </div>
  </article>
</template>

<style scoped>
.rule-card { display: grid; gap: 12px; padding: 14px; border-radius: 16px; border: 1px solid var(--border-color); background: rgba(255, 255, 255, 0.03); }
.rule-card__top, .rule-card__summary, .rule-card__actions { display: flex; gap: 10px; flex-wrap: wrap; }
.rule-card__top { align-items: center; justify-content: space-between; }
.rule-card__name { font-size: 0.96rem; font-weight: 700; color: var(--text-primary); }
.rule-card__meta { font-size: 0.76rem; line-height: 1.6; color: var(--text-muted); }
.rule-card__summary span, .rule-card__status { padding: 5px 10px; border-radius: 999px; font-size: 0.72rem; }
.rule-card__summary span { border: 1px solid var(--border-color); color: var(--text-secondary); background: rgba(255, 255, 255, 0.04); }
.rule-card__status--ok { color: var(--accent-primary); background: rgba(0, 212, 170, 0.1); }
.rule-card__status--warn { color: var(--accent-danger); background: rgba(239, 68, 68, 0.1); }
.rule-card__actions { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); }
.action-card { display: flex; gap: 10px; align-items: flex-start; padding: 12px; border-radius: 14px; border: 1px solid var(--border-color); background: rgba(255, 255, 255, 0.05); color: var(--text-primary); text-align: left; }
.action-card--primary { border-color: rgba(127, 142, 255, 0.42); background: rgba(127, 142, 255, 0.16); }
.action-card:disabled { opacity: 0.45; cursor: not-allowed; }
.action-card__icon { width: 34px; height: 34px; display: inline-flex; align-items: center; justify-content: center; border-radius: 12px; background: rgba(255, 255, 255, 0.08); }
.action-card__body { display: grid; gap: 4px; }
.action-card__body strong { color: var(--text-primary); }
.action-card__body small { line-height: 1.6; color: var(--text-secondary); }
.rule-card__form { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.rule-field { padding: 10px 12px; border-radius: 10px; border: 1px solid var(--border-color); background: rgba(255, 255, 255, 0.04); color: var(--text-primary); }
.rule-field--wide { grid-column: 1 / -1; }
@media (max-width: 980px) {
  .rule-card__actions, .rule-card__form { grid-template-columns: 1fr; }
  .rule-card__top { align-items: flex-start; }
}
</style>

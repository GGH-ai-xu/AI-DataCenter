<script setup>
/**
 * UserRulesGrid - 用户额度规则配置面板
 * 从 TaskManager.vue 提取
 */
import { ref, watch } from 'vue'

const props = defineProps({
  users: { type: Array, default: () => [] },
})

const emit = defineEmits(['save', 'reset'])

const roleOptions = {
  protected: '保护用户',
  member: '普通用户',
  restricted: '受限用户',
}

const ruleSaving = ref({})
const ruleDrafts = ref({})

function buildRuleDraft(user) {
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

function syncDrafts(users) {
  const next = { ...ruleDrafts.value }
  for (const user of users || []) {
    next[user.username] = buildRuleDraft(user)
  }
  ruleDrafts.value = next
}

watch(() => props.users, (users) => syncDrafts(users), { immediate: true })

async function saveRule(user) {
  const draft = ruleDrafts.value[user.username]
  if (!draft) return
  ruleSaving.value[user.username] = true
  emit('save', {
    username: user.username,
    role: draft.role,
    max_tasks: Number(draft.max_tasks),
    max_gpu_count: Number(draft.max_gpu_count),
    max_memory_gb: Number(draft.max_memory_gb),
    allow_preempt: !!draft.allow_preempt,
    note: draft.note || '',
  })
  ruleSaving.value[user.username] = false
}

async function resetRule(user) {
  if (!user?.governance_rule) return
  ruleSaving.value[user.username] = true
  emit('reset', user.username)
  ruleSaving.value[user.username] = false
}
</script>

<template>
  <section v-if="users.length" class="tech-card rules-panel">
    <div class="rules-panel__head">
      <div class="panel-card__title">用户额度规则</div>
      <div class="rules-panel__hint">为活跃用户设置任务数、GPU数、显存额度与是否允许让路</div>
    </div>
    <div class="rules-grid">
      <div v-for="user in users" :key="user.username" class="rule-card">
        <div class="rule-card__top">
          <div>
            <div class="rule-card__name">{{ user.username }}</div>
            <div class="rule-card__meta">
              当前 {{ user.task_count }} 个任务 · {{ user.gpu_count }} 张GPU · {{ user.memory_share_pct }}%
            </div>
          </div>
          <span class="rule-card__status" :class="user.violation_count ? 'rule-card__status--warn' : 'rule-card__status--ok'">
            {{ user.violation_count ? `违规 ${user.violation_count}` : '规则内' }}
          </span>
        </div>

        <div v-if="ruleDrafts[user.username]" class="rule-card__form">
          <select v-model="ruleDrafts[user.username].role" class="task-select">
            <option value="protected">{{ roleOptions.protected }}</option>
            <option value="member">{{ roleOptions.member }}</option>
            <option value="restricted">{{ roleOptions.restricted }}</option>
          </select>
          <input v-model.number="ruleDrafts[user.username].max_tasks" class="task-input" type="number" min="1" max="64" placeholder="最多任务" />
          <input v-model.number="ruleDrafts[user.username].max_gpu_count" class="task-input" type="number" min="1" max="16" placeholder="最多GPU" />
          <input v-model.number="ruleDrafts[user.username].max_memory_gb" class="task-input" type="number" min="1" step="0.5" max="1024" placeholder="显存额度(GB)" />
          <select v-model="ruleDrafts[user.username].allow_preempt" class="task-select">
            <option :value="true">允许让路</option>
            <option :value="false">保护任务</option>
          </select>
          <input v-model="ruleDrafts[user.username].note" class="task-input" type="text" placeholder="备注" />
        </div>

        <div class="rule-card__actions">
          <button class="btn-tech" :disabled="ruleSaving[user.username]" @click="saveRule(user)">
            {{ ruleSaving[user.username] ? '保存中...' : '保存规则' }}
          </button>
          <button class="btn-tech" :disabled="ruleSaving[user.username] || !user.governance_rule" @click="resetRule(user)">
            恢复默认
          </button>
        </div>
      </div>
    </div>
  </section>

  <section v-else class="tech-card rules-panel rules-panel--empty">
    <div class="panel-card__title">用户额度规则</div>
    <div class="panel-card__item">当前没有活跃用户需要配置规则。</div>
  </section>
</template>

<style scoped>
.rules-panel { padding: 18px; margin-bottom: 14px; }
.rules-panel__head { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 4px; }
.rules-panel__hint { font-size: 0.75rem; color: var(--text-muted); line-height: 1.6; }
.rules-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-top: 12px; }
.rule-card { padding: 14px; border-radius: 12px; background: rgba(91,75,140,0.03); border: 1px solid rgba(91,75,140,0.08); }
.rule-card__top { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 10px; }
.rule-card__name { font-size: 0.92rem; font-weight: 700; color: var(--text-primary); }
.rule-card__meta { font-size: 0.75rem; color: var(--text-muted); line-height: 1.6; }
.rule-card__status { padding: 4px 10px; border-radius: 999px; font-size: 0.6875rem; font-weight: 700; }
.rule-card__status--ok { color: #2E8B57; background: rgba(46,139,87,0.08); }
.rule-card__status--warn { color: #C41E3A; background: rgba(196,30,58,0.08); }
.rule-card__form { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-bottom: 10px; }
.rule-card__actions { display: flex; gap: 8px; flex-wrap: wrap; }
.task-input, .task-select { padding: 8px 10px; border-radius: 8px; border: 1px solid var(--border-color); background: rgba(255,255,255,0.55); color: var(--text-primary); font-size: 0.8125rem; }
.task-input { flex: 1; }

@media (max-width: 1400px) { .rules-grid { grid-template-columns: 1fr; } }
@media (max-width: 860px) {
  .rule-card__top, .rule-card__actions { flex-direction: column; align-items: stretch; }
  .rule-card__form { grid-template-columns: 1fr; }
}
</style>

<script setup>
/**
 * TaskManager.vue - 任务治理页
 * 在原有任务管理基础上补充公平治理、让路候选与用户占用画像
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useAppStore } from '../stores/app'
import { deleteGovernanceRule, exportGovernanceReport, getFairnessGovernance, getTasks, pauseTask, resumeTask, saveGovernanceRule, terminateTask, setTaskPriority } from '../services/api'

const store = useAppStore()
const actionLoading = ref({})
const exporting = ref(false)
const ruleSaving = ref({})
const keyword = ref('')
const selectedPriority = ref('all')
const ruleDrafts = ref({})
const fairnessState = ref({
  overview: {
    fairness_index: 100,
    level: 'balanced',
    summary: '当前共享较均衡。',
    dominant_user: null,
    highest_share_pct: 0,
    reclaimable_candidates: 0,
  },
  users: [],
  yield_candidates: [],
  recommendations: [],
})
let refreshTimer = null

const fmtMem = (bytes) => ((bytes || 0) / 1073741824).toFixed(1) + ' GB'

const priorityColors = {
  urgent: { bg: 'rgba(196,30,58,0.12)', color: '#C41E3A', label: '紧急', tip: '关键任务，预算紧张时优先保留' },
  normal: { bg: 'rgba(58,95,75,0.12)', color: '#3A5F4B', label: '普通', tip: '常规任务，可适度压缩功耗' },
  deferrable: { bg: 'rgba(148,163,184,0.12)', color: '#666666', label: '可延迟', tip: '预算紧张时优先让路' },
}

const roleOptions = {
  protected: '保护用户',
  member: '普通用户',
  restricted: '受限用户',
}

const filteredProcesses = computed(() => {
  const term = keyword.value.trim().toLowerCase()
  return store.processes.filter((proc) => {
    const priority = proc.priority || 'normal'
    const text = `${proc.pid} ${proc.name || ''} ${proc.username || ''} ${proc.command || ''}`.toLowerCase()
    const matchPriority = selectedPriority.value === 'all' || selectedPriority.value === priority
    const matchKeyword = !term || text.includes(term)
    return matchPriority && matchKeyword
  })
})

const userCount = computed(() => new Set(store.processes.map(proc => proc.username || 'unknown')).size)
const urgentCount = computed(() => store.processes.filter(proc => (proc.priority || 'normal') === 'urgent').length)
const deferrableCount = computed(() => store.processes.filter(proc => (proc.priority || 'normal') === 'deferrable').length)
const totalGpuMemory = computed(() =>
  store.processes.reduce((sum, proc) => sum + (proc.gpu_memory_used || 0), 0)
)
const fairnessOverview = computed(() => fairnessState.value.overview || {})
const fairnessUsers = computed(() => fairnessState.value.users || [])
const yieldCandidates = computed(() => fairnessState.value.yield_candidates || [])

const userSummary = computed(() => {
  if (fairnessUsers.value.length) {
    return fairnessUsers.value.slice(0, 4).map((user) => ({
      username: user.username,
      tasks: user.task_count,
      memory: user.total_memory,
      share: user.memory_share_pct,
      level: user.level,
      action: user.recommended_action,
    }))
  }

  const map = new Map()
  for (const proc of store.processes) {
    const key = proc.username || 'unknown'
    if (!map.has(key)) {
      map.set(key, { username: key, tasks: 0, memory: 0 })
    }
    const entry = map.get(key)
    entry.tasks += 1
    entry.memory += proc.gpu_memory_used || 0
  }
  return [...map.values()].sort((a, b) => b.memory - a.memory).slice(0, 4)
})

const governanceNarrative = computed(() => {
  if ((fairnessOverview.value.violation_user_count || 0) > 0) {
    return `当前已有 ${fairnessOverview.value.violation_user_count} 个用户触发额度规则，建议优先处理规则违规与让路任务。`
  }
  if (fairnessOverview.value.level === 'critical') {
    return `当前共享公平性偏弱，${fairnessOverview.value.dominant_user || '部分用户'}占用显著偏高，建议优先处理可延迟任务。`
  }
  if (fairnessOverview.value.level === 'watch') {
    return '当前资源开始向少数用户集中，适合提前做额度提醒和让路治理。'
  }
  return '当前任务共享较均衡，平台可继续以监测、分级和轻量治理为主。'
})

function buildRuleDraft(user) {
  const rule = user.governance_rule || {}
  return {
    username: user.username,
    role: rule.role || 'member',
    max_tasks: rule.max_tasks ?? 4,
    max_gpu_count: rule.max_gpu_count ?? 1,
    max_memory_gb: rule.max_memory_gb ?? 8,
    allow_preempt: rule.allow_preempt ?? true,
    note: rule.note || '',
  }
}

function syncRuleDrafts(users) {
  const next = { ...ruleDrafts.value }
  for (const user of users || []) {
    next[user.username] = buildRuleDraft(user)
  }
  ruleDrafts.value = next
}

async function loadTaskGovernance() {
  try {
    const [{ data: taskData }, { data: fairnessData }] = await Promise.all([
      getTasks(),
      getFairnessGovernance(),
    ])
    store.processes = taskData?.processes || []
    fairnessState.value = fairnessData
    syncRuleDrafts(fairnessData?.users || [])
  } catch (e) {
    console.error(e)
  }
}

async function doAction(procId, action) {
  actionLoading.value[`${procId}-${action}`] = true
  try {
    if (action === 'pause') await pauseTask(procId)
    else if (action === 'resume') await resumeTask(procId)
    else if (action === 'terminate') await terminateTask(procId)
  } catch (e) {
    console.error(e)
  }
  actionLoading.value[`${procId}-${action}`] = false
  await loadTaskGovernance()
}

async function changePriority(procId, priority) {
  try {
    await setTaskPriority(procId, priority)
    await loadTaskGovernance()
  } catch (e) {
    console.error(e)
  }
}

async function saveRuleForUser(user) {
  const draft = ruleDrafts.value[user.username]
  if (!draft) return
  ruleSaving.value[user.username] = true
  try {
    await saveGovernanceRule({
      username: user.username,
      role: draft.role,
      max_tasks: Number(draft.max_tasks),
      max_gpu_count: Number(draft.max_gpu_count),
      max_memory_gb: Number(draft.max_memory_gb),
      allow_preempt: !!draft.allow_preempt,
      note: draft.note || '',
    })
    await loadTaskGovernance()
  } catch (e) {
    console.error(e)
  }
  ruleSaving.value[user.username] = false
}

async function resetRuleForUser(user) {
  if (!user?.governance_rule) return
  ruleSaving.value[user.username] = true
  try {
    await deleteGovernanceRule(user.username)
    await loadTaskGovernance()
  } catch (e) {
    console.error(e)
  }
  ruleSaving.value[user.username] = false
}

async function doExportGovernance(fmt = 'markdown') {
  exporting.value = true
  try {
    const res = await exportGovernanceReport(fmt)
    const blob = new Blob([res.data], { type: fmt === 'html' ? 'text/html' : 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = fmt === 'html' ? 'governance-report.html' : 'governance-report.md'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  } catch (e) {
    console.error(e)
  }
  exporting.value = false
}

onMounted(() => {
  loadTaskGovernance()
  refreshTimer = setInterval(loadTaskGovernance, 30000)
})

onUnmounted(() => {
  clearInterval(refreshTimer)
})
</script>

<template>
  <div class="task-page ink-page-shell">
    <section class="task-hero tech-card">
      <div>
        <div class="task-hero__eyebrow">任务治理中心</div>
        <h2 class="task-hero__title">把 GPU 进程从“看到”升级到“分级、让路、干预、追踪”</h2>
        <p class="task-hero__desc">
          {{ governanceNarrative }}
        </p>
      </div>
      <div class="task-hero__actions">
        <button class="btn-tech" :disabled="exporting" @click="doExportGovernance('markdown')">
          {{ exporting ? '导出中...' : '导出治理报告' }}
        </button>
        <div class="task-hero__warn">注意：本页操作会对真实进程立即生效</div>
      </div>
    </section>

    <div class="task-stats">
      <div class="task-stat tech-card">
        <div class="task-stat__label">当前任务总数</div>
        <div class="task-stat__value stat-value">{{ store.processes.length }}</div>
        <div class="task-stat__hint">GPU占用中的全部进程</div>
      </div>
      <div class="task-stat tech-card">
        <div class="task-stat__label">活跃用户</div>
        <div class="task-stat__value stat-value">{{ userCount }}</div>
        <div class="task-stat__hint">共享实验室资源的使用者</div>
      </div>
      <div class="task-stat tech-card">
        <div class="task-stat__label">紧急任务</div>
        <div class="task-stat__value stat-value" style="color:#C41E3A">{{ urgentCount }}</div>
        <div class="task-stat__hint">预算紧张时优先保障</div>
      </div>
      <div class="task-stat tech-card">
        <div class="task-stat__label">可延迟任务</div>
        <div class="task-stat__value stat-value" style="color:#666">{{ deferrableCount }}</div>
        <div class="task-stat__hint">高峰期优先让路</div>
      </div>
      <div class="task-stat tech-card">
        <div class="task-stat__label">总显存占用</div>
        <div class="task-stat__value stat-value">{{ fmtMem(totalGpuMemory) }}</div>
        <div class="task-stat__hint">用于评估资源紧张程度</div>
      </div>
      <div class="task-stat tech-card">
        <div class="task-stat__label">公平治理指数</div>
        <div class="task-stat__value stat-value" :style="{ color: fairnessOverview.level === 'critical' ? '#C41E3A' : fairnessOverview.level === 'watch' ? '#B8860B' : '#2E8B57' }">
          {{ fairnessOverview.fairness_index ?? 0 }}
        </div>
        <div class="task-stat__hint">{{ fairnessOverview.summary }}</div>
      </div>
    </div>

    <div class="task-grid">
      <div class="tech-card task-side-card">
        <div class="section-title" style="margin-bottom: 12px">优先级规则</div>
        <div
          v-for="(item, key) in priorityColors"
          :key="key"
          class="priority-rule"
          :style="{ background: item.bg }"
        >
          <div class="priority-rule__head">
            <span class="priority-rule__tag" :style="{ color: item.color }">{{ item.label }}</span>
            <span class="priority-rule__count stat-value">{{ store.processes.filter(proc => (proc.priority || 'normal') === key).length }}</span>
          </div>
          <div class="priority-rule__tip">{{ item.tip }}</div>
        </div>
      </div>

      <div class="tech-card task-side-card">
        <div class="section-title" style="margin-bottom: 12px">用户占用概览</div>
        <div v-if="userSummary.length" class="user-summary">
          <div v-for="user in userSummary" :key="user.username" class="user-summary__item">
            <div class="user-summary__top">
              <span class="user-summary__name">{{ user.username }}</span>
              <span class="user-summary__tasks">{{ user.tasks }} 个任务<span v-if="user.share !== undefined"> · {{ user.share }}%</span></span>
            </div>
            <div class="user-summary__mem">{{ fmtMem(user.memory) }} GPU显存</div>
            <div v-if="user.action" class="user-summary__action">{{ user.action }}</div>
          </div>
        </div>
        <div v-else class="task-empty">当前无GPU进程</div>
      </div>

      <div class="tech-card task-side-card">
        <div class="section-title" style="margin-bottom: 12px">公平治理建议</div>
        <div class="fairness-score-box">
          <div class="fairness-score-box__value stat-value">{{ fairnessOverview.fairness_index ?? 0 }}</div>
          <div class="fairness-score-box__meta">
            <div>主导用户：{{ fairnessOverview.dominant_user || '无明显集中' }}</div>
            <div>最高占用：{{ fairnessOverview.highest_share_pct || 0 }}%</div>
            <div>建议让路：{{ fairnessOverview.reclaimable_candidates || 0 }} 个任务</div>
          </div>
        </div>
        <div class="fairness-rec-list">
          <div v-for="(item, index) in fairnessState.recommendations || []" :key="index" class="fairness-rec-item">
            {{ item }}
          </div>
        </div>
      </div>
    </div>

    <div class="tech-card yield-panel" v-if="yieldCandidates.length">
      <div class="yield-panel__header">
        <div class="section-title">建议让路任务</div>
        <div class="task-toolbar__right">按优先级、用户占用和显存压力综合排序</div>
      </div>
      <div class="yield-list">
        <div v-for="candidate in yieldCandidates" :key="candidate.pid" class="yield-item">
          <div class="yield-item__top">
            <span class="yield-item__pid">PID {{ candidate.pid }}</span>
            <span class="yield-item__user">{{ candidate.username }}</span>
            <span class="yield-item__priority" :style="{ color: priorityColors[candidate.priority || 'normal'].color, background: priorityColors[candidate.priority || 'normal'].bg }">
              {{ priorityColors[candidate.priority || 'normal'].label }}
            </span>
            <span class="yield-item__score">让路分 {{ candidate.yield_score }}</span>
          </div>
          <div class="yield-item__reason">{{ candidate.yield_reason }}</div>
          <div class="yield-item__meta">GPU {{ candidate.gpu_index }} · {{ fmtMem(candidate.gpu_memory_used) }} · {{ candidate.name || 'unknown' }}</div>
        </div>
      </div>
    </div>

    <div class="tech-card rule-panel" v-if="fairnessUsers.length">
      <div class="yield-panel__header">
        <div class="section-title">用户额度规则</div>
        <div class="task-toolbar__right">为活跃用户设置任务数、GPU数、显存额度与是否允许让路</div>
      </div>
      <div class="rule-grid">
        <div v-for="user in fairnessUsers" :key="user.username" class="rule-card">
          <div class="rule-card__top">
            <div>
              <div class="rule-card__name">{{ user.username }}</div>
              <div class="rule-card__meta">
                当前 {{ user.task_count }} 个任务 · {{ user.gpu_count }} 张GPU · {{ user.memory_share_pct }}% 占用
              </div>
            </div>
            <span
              class="rule-card__status"
              :class="user.violation_count ? 'rule-card__status--warn' : 'rule-card__status--ok'"
            >
              {{ user.violation_count ? `违规 ${user.violation_count}` : '规则内' }}
            </span>
          </div>

          <div class="rule-form" v-if="ruleDrafts[user.username]">
            <label class="rule-field">
              <span>角色</span>
              <select v-model="ruleDrafts[user.username].role" class="task-select">
                <option value="protected">{{ roleOptions.protected }}</option>
                <option value="member">{{ roleOptions.member }}</option>
                <option value="restricted">{{ roleOptions.restricted }}</option>
              </select>
            </label>
            <label class="rule-field">
              <span>最多任务</span>
              <input v-model.number="ruleDrafts[user.username].max_tasks" class="task-input" type="number" min="1" max="64" />
            </label>
            <label class="rule-field">
              <span>最多GPU</span>
              <input v-model.number="ruleDrafts[user.username].max_gpu_count" class="task-input" type="number" min="1" max="16" />
            </label>
            <label class="rule-field">
              <span>显存额度(GB)</span>
              <input v-model.number="ruleDrafts[user.username].max_memory_gb" class="task-input" type="number" min="1" step="0.5" max="1024" />
            </label>
            <label class="rule-field">
              <span>允许让路</span>
              <select v-model="ruleDrafts[user.username].allow_preempt" class="task-select">
                <option :value="true">允许</option>
                <option :value="false">保护</option>
              </select>
            </label>
            <label class="rule-field rule-field--full">
              <span>备注</span>
              <input v-model="ruleDrafts[user.username].note" class="task-input" type="text" placeholder="如：教师任务 / 答辩周重点保障" />
            </label>
          </div>

          <div v-if="user.violations?.length" class="rule-violations">
            <span v-for="(item, index) in user.violations" :key="index" class="rule-violation">
              {{ item }}
            </span>
          </div>

          <div class="rule-card__actions">
            <div class="rule-card__action-buttons">
              <button class="btn-tech" :disabled="ruleSaving[user.username]" @click="saveRuleForUser(user)">
                {{ ruleSaving[user.username] ? '保存中...' : '保存规则' }}
              </button>
              <button class="btn-tech" :disabled="ruleSaving[user.username] || !user.governance_rule" @click="resetRuleForUser(user)">
                恢复默认
              </button>
            </div>
            <span class="rule-card__hint">{{ user.recommended_action }}</span>
          </div>
        </div>
      </div>
    </div>

    <div class="task-toolbar tech-card">
      <div class="task-toolbar__left">
        <input v-model="keyword" class="task-input" placeholder="搜索 PID / 用户 / 进程名 / 命令" />
        <select v-model="selectedPriority" class="task-select">
          <option value="all">全部优先级</option>
          <option value="urgent">紧急</option>
          <option value="normal">普通</option>
          <option value="deferrable">可延迟</option>
        </select>
      </div>
      <div class="task-toolbar__right">
        <span>当前筛选结果 {{ filteredProcesses.length }} 条</span>
      </div>
    </div>

    <div class="task-table tech-card">
      <table>
        <thead>
          <tr>
            <th>PID</th>
            <th>GPU</th>
            <th>进程名</th>
            <th>用户</th>
            <th>GPU显存</th>
            <th>CPU</th>
            <th>优先级</th>
            <th>命令</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="proc in filteredProcesses" :key="proc.pid">
            <td class="stat-value" style="color: var(--accent-primary)">{{ proc.pid }}</td>
            <td><span class="gpu-tag">GPU {{ proc.gpu_index }}</span></td>
            <td>{{ proc.name }}</td>
            <td style="color: var(--text-muted)">{{ proc.username }}</td>
            <td class="stat-value">{{ fmtMem(proc.gpu_memory_used) }}</td>
            <td class="stat-value">{{ proc.cpu_percent?.toFixed(1) }}%</td>
            <td>
              <select
                class="priority-select"
                :value="proc.priority || 'normal'"
                @change="changePriority(proc.pid, $event.target.value)"
                :style="{ color: priorityColors[proc.priority || 'normal'].color, background: priorityColors[proc.priority || 'normal'].bg }"
              >
                <option value="urgent">紧急</option>
                <option value="normal">普通</option>
                <option value="deferrable">可延迟</option>
              </select>
            </td>
            <td class="task-command">{{ proc.command || '-' }}</td>
            <td>
              <div class="task-actions">
                <button class="btn-tech" :disabled="actionLoading[`${proc.pid}-pause`]" style="padding: 4px 10px; font-size: 0.75rem" @click="doAction(proc.pid, 'pause')">暂停</button>
                <button class="btn-tech" :disabled="actionLoading[`${proc.pid}-resume`]" style="padding: 4px 10px; font-size: 0.75rem" @click="doAction(proc.pid, 'resume')">恢复</button>
                <button class="btn-tech btn-tech--danger" :disabled="actionLoading[`${proc.pid}-terminate`]" style="padding: 4px 10px; font-size: 0.75rem" @click="doAction(proc.pid, 'terminate')">终止</button>
              </div>
            </td>
          </tr>
          <tr v-if="!filteredProcesses.length">
            <td colspan="9" class="task-empty">暂无匹配的GPU进程</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.task-page { max-width: 1460px; margin: 0 auto; }

.task-hero {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 22px 24px;
  margin-bottom: 16px;
}

.task-hero__actions {
  display: flex;
  align-items: flex-start;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.task-hero__eyebrow {
  font-size: 0.75rem;
  color: var(--text-muted);
  letter-spacing: 0.12em;
  margin-bottom: 8px;
}

.task-hero__title {
  font-size: 1.5rem;
  line-height: 1.4;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.task-hero__desc {
  font-size: 0.875rem;
  color: var(--text-secondary);
  line-height: 1.7;
}

.task-hero__warn {
  align-self: flex-start;
  font-size: 0.75rem;
  color: #B8860B;
  background: rgba(184,134,11,0.08);
  border: 1px solid rgba(184,134,11,0.16);
  padding: 8px 12px;
  border-radius: 999px;
  white-space: nowrap;
}

.task-stats {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
  margin-bottom: 14px;
}

.task-stat {
  padding: 16px;
}

.task-stat__label,
.task-stat__hint {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.task-stat__value {
  font-size: 1.8rem;
  margin: 6px 0 4px;
}

.task-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
  margin-bottom: 14px;
}

.task-side-card {
  padding: 18px;
}

.priority-rule {
  padding: 12px 14px;
  border-radius: 10px;
  margin-bottom: 10px;
}

.priority-rule__head,
.user-summary__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.priority-rule__tag {
  font-size: 0.8125rem;
  font-weight: 600;
}

.priority-rule__count {
  font-size: 1rem;
}

.priority-rule__tip,
.user-summary__mem,
.user-summary__tasks,
.task-toolbar__right {
  font-size: 0.75rem;
  color: var(--text-muted);
  line-height: 1.6;
}

.user-summary {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.user-summary__item {
  padding: 12px 14px;
  border-radius: 10px;
  background: rgba(58,95,75,0.04);
  border: 1px solid rgba(58,95,75,0.08);
}

.user-summary__name {
  color: var(--text-primary);
  font-size: 0.875rem;
  font-weight: 600;
}

.user-summary__action {
  margin-top: 6px;
  font-size: 0.75rem;
  color: var(--text-secondary);
  line-height: 1.6;
}

.fairness-score-box {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px;
  background: rgba(91,75,140,0.04);
  border: 1px solid rgba(91,75,140,0.08);
  border-radius: 10px;
  margin-bottom: 12px;
}

.fairness-score-box__value {
  font-size: 2rem;
  color: #5B4B8C;
}

.fairness-score-box__meta {
  font-size: 0.75rem;
  color: var(--text-secondary);
  line-height: 1.7;
}

.fairness-rec-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.fairness-rec-item {
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(58,95,75,0.04);
  border: 1px solid rgba(58,95,75,0.08);
  font-size: 0.75rem;
  color: var(--text-secondary);
  line-height: 1.7;
}

.yield-panel {
  padding: 18px;
  margin-bottom: 14px;
}

.yield-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.yield-list {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.yield-item {
  padding: 14px;
  border-radius: 10px;
  background: rgba(196,30,58,0.03);
  border: 1px solid rgba(196,30,58,0.1);
}

.yield-item__top {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.yield-item__pid {
  font-size: 0.75rem;
  font-weight: 700;
  color: #C41E3A;
}

.yield-item__user,
.yield-item__score,
.yield-item__meta {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.yield-item__priority {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 0.6875rem;
  font-weight: 600;
}

.yield-item__reason {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 6px;
}

.rule-panel {
  padding: 18px;
  margin-bottom: 14px;
}

.rule-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.rule-card {
  padding: 16px;
  border-radius: 12px;
  background: rgba(91,75,140,0.03);
  border: 1px solid rgba(91,75,140,0.08);
}

.rule-card__top,
.rule-card__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.rule-card__action-buttons {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.rule-card__top {
  margin-bottom: 12px;
}

.rule-card__name {
  font-size: 0.95rem;
  color: var(--text-primary);
  font-weight: 700;
}

.rule-card__meta,
.rule-card__hint {
  font-size: 0.75rem;
  color: var(--text-muted);
  line-height: 1.6;
}

.rule-card__status {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 0.6875rem;
  font-weight: 700;
}

.rule-card__status--ok {
  color: #2E8B57;
  background: rgba(46,139,87,0.08);
}

.rule-card__status--warn {
  color: #C41E3A;
  background: rgba(196,30,58,0.08);
}

.rule-form {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px 12px;
  margin-bottom: 12px;
}

.rule-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.rule-field span {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.rule-field--full {
  grid-column: 1 / -1;
}

.rule-violations {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.rule-violation {
  font-size: 0.6875rem;
  color: #C41E3A;
  background: rgba(196,30,58,0.08);
  border: 1px solid rgba(196,30,58,0.12);
  padding: 4px 8px;
  border-radius: 999px;
}

.task-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  margin-bottom: 14px;
}

.task-toolbar__left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
}

.task-input,
.task-select,
.priority-select {
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background: rgba(255,255,255,0.55);
  color: var(--text-primary);
  font-size: 0.8125rem;
}

.task-input {
  flex: 1;
}

.task-table { overflow-x: auto; }

table { width: 100%; border-collapse: collapse; }

th {
  text-align: left;
  padding: 12px 16px;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid var(--border-color);
}

td {
  padding: 12px 16px;
  font-size: 0.8125rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
  vertical-align: top;
}

tr:hover td { background: rgba(58, 95, 75, 0.03); }

.gpu-tag {
  font-size: 0.6875rem;
  font-weight: 600;
  color: var(--accent-primary);
  background: rgba(58, 95, 75, 0.1);
  padding: 2px 8px;
  border-radius: 4px;
}

.task-command {
  max-width: 320px;
  color: var(--text-secondary);
  line-height: 1.6;
  word-break: break-word;
}

.task-actions {
  display: flex;
  gap: 6px;
}

.task-empty {
  text-align: center;
  color: var(--text-muted);
  padding: 40px 16px;
}

@media (max-width: 1400px) {
  .task-stats { grid-template-columns: repeat(3, 1fr); }
  .task-grid { grid-template-columns: 1fr; }
  .yield-list { grid-template-columns: 1fr; }
  .rule-grid { grid-template-columns: 1fr; }
}

@media (max-width: 860px) {
  .task-hero,
  .task-hero__actions,
  .task-toolbar,
  .task-toolbar__left,
  .task-actions,
  .yield-panel__header,
  .rule-card__top,
  .rule-card__actions,
  .rule-card__action-buttons {
    flex-direction: column;
    align-items: stretch;
  }

  .task-stats { grid-template-columns: 1fr; }
  .rule-form { grid-template-columns: 1fr; }
}
</style>

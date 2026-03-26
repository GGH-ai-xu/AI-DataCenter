<script setup>
/**
 * Scheduler.vue - 智能调度页
 * 手动/自动调度控制、总功率预算治理、功耗限制设置、AI调度策略、能耗报告
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useAppStore } from '../stores/app'
import {
  getSchedulerStatus,
  getScheduleReport,
  runScheduleOnce,
  setManualPowerLimit,
  setPowerBudget,
  toggleAutoSchedule,
} from '../services/api'

const store = useAppStore()
const autoEnabled = ref(false)
const timePeriod = ref('')
const powerInputs = ref({})
const scheduleResult = ref(null)
const report = ref('')
const reportLoading = ref(false)
const scheduleLoading = ref(false)
const executionMode = ref('dry_run')
const riskAcknowledged = ref(false)
const actionNotice = ref(null)
const budget = ref({
  enabled: false,
  total_power_budget: 1200,
  current_total_power: 0,
  remaining_power: 1200,
  usage_pct: 0,
  is_exceeded: false,
  managed_gpu_count: 0,
  last_actions: [],
})
const budgetForm = ref({
  enabled: false,
  total_power_budget: 1200,
})
let refreshTimer = null

const currentClusterPower = computed(() => {
  const backendValue = Number(budget.value.current_total_power || 0)
  return backendValue > 0 ? backendValue : store.totalPower
})

const combinedResults = computed(() =>
  []
    .concat(scheduleResult.value?.rule_results || [])
    .concat(scheduleResult.value?.budget_results || [])
    .concat(scheduleResult.value?.ai_results || [])
)

const executionSummary = computed(() =>
  executionMode.value === 'real'
    ? '当前为真实执行模式，调度与单卡限功率会立即作用于真实设备。'
    : '当前为演练模式，只输出动作预演，不会执行真实控制。'
)

const budgetFillStyle = computed(() => {
  const width = Math.min(100, Math.max(0, budget.value.usage_pct || 0))
  const background = budget.value.is_exceeded
    ? 'linear-gradient(90deg, #C41E3A, #F97316)'
    : 'linear-gradient(90deg, #2E8B57, #3A5F4B)'
  return { width: `${width}%`, background }
})

function applyBudgetState(nextBudget) {
  const merged = {
    enabled: false,
    total_power_budget: 1200,
    current_total_power: 0,
    remaining_power: 1200,
    usage_pct: 0,
    is_exceeded: false,
    managed_gpu_count: 0,
    last_actions: [],
    ...(nextBudget || {}),
  }
  budget.value = merged
  budgetForm.value = {
    enabled: merged.enabled,
    total_power_budget: merged.total_power_budget,
  }
}

function setActionNotice(tone, title, detail) {
  actionNotice.value = { tone, title, detail, ts: Date.now() }
}

function buildExecutionOptions() {
  const isReal = executionMode.value === 'real'
  return {
    dry_run: !isReal,
    acknowledge_risk: isReal && riskAcknowledged.value,
  }
}

function ensureRiskAcknowledged(label) {
  if (executionMode.value !== 'real') return true
  if (riskAcknowledged.value) return true
  setActionNotice('warning', '尚未确认风险', `${label}前请先勾选风险确认。`)
  return false
}

async function loadStatus() {
  try {
    const { data } = await getSchedulerStatus()
    autoEnabled.value = data.auto_enabled
    timePeriod.value = data.time_period_label
    applyBudgetState(data.budget)
  } catch (e) {}
}

async function toggleAuto() {
  const next = !autoEnabled.value
  try {
    await toggleAutoSchedule(next)
    autoEnabled.value = next
    await loadStatus()
  } catch (e) {}
}

async function saveBudget() {
  const limit = parseInt(budgetForm.value.total_power_budget, 10)
  if (!limit || limit < 400 || limit > 5000) return
  try {
    const { data } = await setPowerBudget(budgetForm.value.enabled, limit)
    applyBudgetState(data.budget)
  } catch (e) {}
}

async function setPower(gpuIndex) {
  const val = parseInt(powerInputs.value[gpuIndex])
  if (!val || val < 100 || val > 350) return
  if (!ensureRiskAcknowledged('单卡限功率')) return
  if (executionMode.value === 'real' && !window.confirm(`将把 GPU ${gpuIndex} 的功耗上限设为 ${val}W，是否继续？`)) {
    return
  }
  try {
    const { data } = await setManualPowerLimit(gpuIndex, val, buildExecutionOptions())
    setActionNotice(
      data?.dry_run ? 'warning' : 'ok',
      data?.dry_run ? '已生成限功率预演' : '限功率已写入',
      data?.message || `GPU ${gpuIndex} 目标功耗上限 ${val}W。`,
    )
    await loadStatus()
  } catch (e) {
    setActionNotice(
      'critical',
      '限功率失败',
      e?.response?.data?.detail || e?.message || '单卡功耗控制失败',
    )
  }
}

async function runOnce() {
  if (!ensureRiskAcknowledged('调度执行')) return
  if (executionMode.value === 'real' && !window.confirm('将执行真实调度动作，是否继续？')) {
    return
  }
  scheduleLoading.value = true
  try {
    const { data } = await runScheduleOnce(buildExecutionOptions())
    scheduleResult.value = data
    applyBudgetState(data.budget)
    setActionNotice(
      data?.dry_run ? 'warning' : 'ok',
      data?.dry_run ? '已生成调度预演' : '调度已执行',
      data?.dry_run
        ? '本次返回的是预演动作，不会改动真实任务与功耗上限。'
        : '本次调度已对真实任务与功耗限制生效。',
    )
    await loadStatus()
  } catch (e) {
    scheduleResult.value = { error: '调度执行失败' }
    setActionNotice(
      'critical',
      '调度执行失败',
      e?.response?.data?.detail || e?.message || '调度执行失败',
    )
  }
  scheduleLoading.value = false
}

async function loadReport() {
  reportLoading.value = true
  try {
    const { data } = await getScheduleReport()
    report.value = data.report
  } catch (e) {
    report.value = '报告生成失败'
  }
  reportLoading.value = false
}

function formatActionTarget(action) {
  if (action?.target?.gpu_index !== undefined) {
    return `GPU ${action.target.gpu_index}`
  }
  if (action?.target?.pid !== undefined) {
    return `PID ${action.target.pid}`
  }
  return '集群'
}

function formatActionLabel(action) {
  if (action?.action === 'set_power_limit') return '压缩功耗'
  if (action?.action === 'pause_task') return '暂停任务'
  if (action?.action === 'resume_task') return '恢复任务'
  return action?.action || '调度动作'
}

onMounted(() => {
  loadStatus()
  refreshTimer = setInterval(loadStatus, 8000)
})

onUnmounted(() => {
  clearInterval(refreshTimer)
})
</script>

<template>
  <div class="scheduler-page ink-page-shell">
    <section class="ink-page-head tech-card">
      <div class="ink-page-head__body">
        <div class="ink-page-head__eyebrow">预算治理 · 自动调度 · 单卡功耗控制</div>
        <h2 class="ink-page-head__title">在峰谷之间，为每一瓦功率安排合适的落点</h2>
        <p class="ink-page-head__desc">
          当前时段 {{ timePeriod || '待获取' }}，{{ budget.is_exceeded ? '总预算已有压力，需要更积极的治理动作。' : '整体预算仍有余量，可继续维持监测与轻干预。' }}
          本页负责总预算开关、自动策略、单卡限功与调度回放，是整个治理平台的控制中枢。
        </p>
      </div>
      <div class="ink-page-head__side">
        <div class="ink-page-head__quote">“先定势，再落笔。”</div>
        <div class="ink-inline-meta">
          <span class="status-badge" :class="autoEnabled ? 'status-badge--ok' : 'status-badge--warning'">
            {{ autoEnabled ? '自动治理中' : '手动观测' }}
          </span>
          <span class="status-badge" :class="budget.is_exceeded ? 'status-badge--critical' : 'status-badge--ok'">
            {{ budget.is_exceeded ? '预算紧张' : '预算平稳' }}
          </span>
        </div>
      </div>
    </section>

    <div
      v-if="actionNotice"
      class="sched-notice tech-card"
      :class="`sched-notice--${actionNotice.tone}`"
    >
      <div class="sched-notice__title">{{ actionNotice.title }}</div>
      <div class="sched-notice__desc">{{ actionNotice.detail }}</div>
    </div>

    <div class="sched-grid">
      <!-- 总功率预算 -->
      <div class="tech-card" style="padding: 20px">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px">
          <div class="section-title">总功率预算治理</div>
          <span
            class="status-badge"
            :class="budget.is_exceeded ? 'status-badge--critical' : 'status-badge--ok'"
          >
            {{ budget.is_exceeded ? '超预算' : '预算内' }}
          </span>
        </div>

        <div class="budget-hero">
          <div>
            <div class="budget-hero__label">当前集群总功率</div>
            <div class="budget-hero__value">
              {{ currentClusterPower.toFixed(1) }}<span>W</span>
            </div>
            <div class="budget-hero__sub">预算上限 {{ budget.total_power_budget }}W</div>
          </div>
          <div class="budget-hero__side">
            <div class="budget-hero__usage">{{ budget.usage_pct }}%</div>
            <div class="budget-hero__sub">预算占用</div>
          </div>
        </div>

        <div class="budget-bar">
          <div class="budget-bar__fill" :style="budgetFillStyle"></div>
        </div>

        <div class="budget-meta">
          <span :style="{ color: budget.is_exceeded ? '#C41E3A' : '#2E8B57' }">
            {{ budget.is_exceeded ? `超出 ${Math.abs(budget.remaining_power).toFixed(1)}W` : `剩余 ${budget.remaining_power.toFixed(1)}W` }}
          </span>
          <span>已接管 {{ budget.managed_gpu_count }} 张GPU</span>
        </div>

        <div class="budget-form">
          <label class="budget-form__checkbox">
            <input v-model="budgetForm.enabled" type="checkbox" />
            启用预算治理
          </label>
          <input
            v-model="budgetForm.total_power_budget"
            type="number"
            min="400"
            max="5000"
            class="power-input"
          />
          <button class="btn-tech btn-tech--primary" @click="saveBudget">保存预算</button>
        </div>

        <div v-if="budget.last_actions?.length" class="budget-actions">
          <div class="budget-actions__title">最近预算动作</div>
          <div
            v-for="(action, index) in budget.last_actions"
            :key="index"
            class="budget-action"
          >
            <div class="budget-action__top">
              <span class="budget-action__tag">{{ formatActionLabel(action) }}</span>
              <span class="budget-action__target">{{ formatActionTarget(action) }}</span>
            </div>
            <div class="budget-action__reason">{{ action.reason }}</div>
          </div>
        </div>
      </div>

      <!-- 调度状态卡片 -->
      <div class="tech-card" style="padding: 20px">
        <div class="section-title" style="margin-bottom: 14px">调度器状态</div>
        <div style="display: flex; align-items: center; gap: 16px; margin-bottom: 16px">
          <span style="color: var(--text-secondary); font-size: 0.875rem">自动调度</span>
          <button
            class="toggle-btn"
            :class="{ 'toggle-btn--on': autoEnabled }"
            @click="toggleAuto"
          >
            <span class="toggle-btn__dot"></span>
          </button>
          <span :style="{ color: autoEnabled ? '#2E8B57' : '#C41E3A', fontSize: '0.8125rem' }">
            {{ autoEnabled ? '已启用' : '已禁用' }}
          </span>
        </div>
        <div style="color: var(--text-muted); font-size: 0.8125rem; margin-bottom: 12px">
          当前时段: <span style="color: var(--accent-primary)">{{ timePeriod }}</span>
        </div>
        <div style="color: var(--text-muted); font-size: 0.8125rem; margin-bottom: 12px">
          当前集群功率: <span style="color: var(--text-primary)">{{ currentClusterPower.toFixed(1) }}W</span>
        </div>
        <div class="execution-panel">
          <div class="execution-panel__switch">
            <button
              class="btn-tech"
              :class="{ 'btn-tech--primary': executionMode === 'dry_run' }"
              @click="executionMode = 'dry_run'"
            >
              演练模式
            </button>
            <button
              class="btn-tech"
              :class="{ 'btn-tech--primary': executionMode === 'real' }"
              @click="executionMode = 'real'"
            >
              真实执行
            </button>
          </div>
          <label v-if="executionMode === 'real'" class="execution-panel__ack">
            <input v-model="riskAcknowledged" type="checkbox" />
            我已确认会直接改动真实任务与功耗限制
          </label>
        </div>
        <div style="color: #B8860B; font-size: 0.75rem; margin-bottom: 12px; line-height: 1.7">
          {{ executionSummary }}
        </div>
        <button class="btn-tech btn-tech--primary" @click="runOnce" :disabled="scheduleLoading">
          {{ scheduleLoading ? '执行中...' : executionMode === 'real' ? '执行一次真实调度' : '演练一次调度' }}
        </button>
      </div>

      <!-- 功耗控制卡片 -->
      <div class="tech-card" style="padding: 20px">
        <div class="section-title" style="margin-bottom: 14px">手动功耗控制</div>
        <div v-for="gpu in store.gpus" :key="gpu.index" class="power-row">
          <span class="gpu-tag">GPU {{ gpu.index }}</span>
          <span class="stat-value" style="font-size: 0.875rem; min-width: 60px">{{ gpu.power_usage?.toFixed(0) }}W</span>
          <input
            type="range"
            min="100"
            max="350"
            :value="gpu.power_limit"
            @input="powerInputs[gpu.index] = $event.target.value"
            class="power-slider"
          />
          <input
            type="number"
            :value="powerInputs[gpu.index] || gpu.power_limit?.toFixed(0)"
            @input="powerInputs[gpu.index] = $event.target.value"
            min="100"
            max="350"
            class="power-input"
          />
          <button class="btn-tech" style="padding: 4px 12px; font-size: 0.75rem" @click="setPower(gpu.index)">设置</button>
        </div>
        <div v-if="!store.gpus.length" style="color: var(--text-muted); font-size: 0.8125rem; padding: 20px; text-align: center">等待GPU数据...</div>
      </div>

      <!-- 调度结果 -->
      <div class="tech-card" style="padding: 20px" v-if="scheduleResult">
        <div class="section-title" style="margin-bottom: 14px">
          {{ scheduleResult.dry_run ? '调度预演结果' : '调度执行结果' }}
        </div>
        <div v-if="scheduleResult.ai_strategy" style="margin-bottom: 12px">
          <div style="color: var(--accent-primary); font-size: 0.8125rem; margin-bottom: 6px">AI策略摘要</div>
          <div style="color: var(--text-secondary); font-size: 0.8125rem">{{ scheduleResult.ai_strategy.summary }}</div>
          <div v-if="scheduleResult.ai_strategy.estimated_power_saving" style="color: #2E8B57; font-size: 0.8125rem; margin-top: 4px">
            理论节能: {{ scheduleResult.ai_strategy.estimated_power_saving }}W
          </div>
        </div>
        <div
          v-if="scheduleResult.budget_actions?.length"
          style="color: var(--text-muted); font-size: 0.75rem; margin-bottom: 8px"
        >
          预算治理动作 {{ scheduleResult.budget_actions.length }} 条
        </div>
        <div
          v-for="(r, i) in combinedResults"
          :key="i"
          class="result-item"
          :class="r.success ? 'result-item--ok' : 'result-item--fail'"
        >
          <div>
            <div>{{ formatActionLabel(r) }}</div>
            <div class="result-item__reason">{{ r.reason }}</div>
          </div>
          <span style="flex: 1; text-align: right">
            {{ r.dry_run ? '预演' : r.success ? '成功' : '失败' }}
          </span>
        </div>
      </div>

      <!-- AI能耗报告 -->
      <div class="tech-card sched-grid__wide" style="padding: 20px">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px">
          <div class="section-title">AI 能耗分析报告</div>
          <button class="btn-tech" @click="loadReport" :disabled="reportLoading">
            {{ reportLoading ? '生成中...' : '生成报告' }}
          </button>
        </div>
        <div v-if="report" class="report-content" v-html="report.replace(/\n/g, '<br>')"></div>
        <div v-else style="color: var(--text-muted); font-size: 0.8125rem; text-align: center; padding: 20px">
          点击"生成报告"获取AI能耗分析
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.scheduler-page { max-width: 1400px; margin: 0 auto; }
.sched-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.sched-grid__wide { grid-column: 1 / -1; }

.sched-notice {
  padding: 14px 16px;
  margin-bottom: 14px;
}

.sched-notice--ok {
  border-color: rgba(46,139,87,0.14);
  background: rgba(46,139,87,0.05);
}

.sched-notice--warning {
  border-color: rgba(184,134,11,0.16);
  background: rgba(212,175,55,0.08);
}

.sched-notice--critical {
  border-color: rgba(196,30,58,0.14);
  background: rgba(196,30,58,0.06);
}

.sched-notice__title {
  font-size: 0.8rem;
  color: var(--text-primary);
  font-weight: 700;
}

.sched-notice__desc {
  margin-top: 6px;
  font-size: 0.78rem;
  color: var(--text-secondary);
  line-height: 1.7;
}

.toggle-btn {
  width: 44px; height: 24px; border-radius: 12px; border: none;
  background: rgba(255, 255, 255, 0.1); cursor: pointer;
  position: relative; transition: background 0.3s;
}
.toggle-btn--on { background: rgba(46,139,87,0.3); }
.toggle-btn__dot {
  position: absolute; top: 3px; left: 3px;
  width: 18px; height: 18px; border-radius: 50%;
  background: #666666; transition: all 0.3s;
}
.toggle-btn--on .toggle-btn__dot { left: 23px; background: #2E8B57; box-shadow: 0 0 8px rgba(46,139,87,0.4); }

.power-row {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.03);
}
.gpu-tag { font-size: 0.6875rem; font-weight: 600; color: var(--accent-primary); background: rgba(58,95,75,0.1); padding: 2px 8px; border-radius: 4px; }

.budget-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.budget-hero__label,
.budget-hero__sub,
.budget-actions__title,
.budget-action__reason,
.budget-meta {
  color: var(--text-muted);
  font-size: 0.75rem;
}

.budget-hero__value {
  font-size: 2rem;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.1;
}

.budget-hero__value span {
  font-size: 0.875rem;
  color: var(--text-muted);
  margin-left: 4px;
}

.budget-hero__side {
  text-align: right;
}

.budget-hero__usage {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--accent-primary);
}

.budget-bar {
  height: 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
  overflow: hidden;
  margin-bottom: 10px;
}

.budget-bar__fill {
  height: 100%;
  border-radius: inherit;
  transition: width 0.3s ease;
}

.budget-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.budget-form {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.budget-form__checkbox {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.8125rem;
  color: var(--text-secondary);
  white-space: nowrap;
}

.budget-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.execution-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.execution-panel__switch {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.execution-panel__ack {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.budget-action {
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(58,95,75,0.04);
  border: 1px solid rgba(58,95,75,0.08);
}

.budget-action__top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.budget-action__tag,
.budget-action__target {
  font-size: 0.6875rem;
  padding: 2px 8px;
  border-radius: 999px;
}

.budget-action__tag {
  color: #2E8B57;
  background: rgba(46,139,87,0.1);
}

.budget-action__target {
  color: var(--accent-primary);
  background: rgba(58,95,75,0.1);
}

.budget-action__reason {
  line-height: 1.6;
}

.power-slider { flex: 1; accent-color: var(--accent-primary); }
.power-input {
  width: 60px; padding: 4px 6px; border-radius: 6px; border: 1px solid var(--border-color);
  background: transparent; color: var(--text-primary); font-size: 0.8125rem; text-align: center;
}

.result-item {
  display: flex; padding: 8px 12px; border-radius: 6px; font-size: 0.8125rem; margin-bottom: 4px;
}
.result-item--ok { background: rgba(46,139,87,0.08); color: #2E8B57; }
.result-item--fail { background: rgba(196,30,58,0.08); color: #C41E3A; }

.result-item__reason {
  margin-top: 4px;
  font-size: 0.72rem;
  color: var(--text-muted);
  line-height: 1.6;
  max-width: 420px;
}

.report-content {
  font-size: 0.8125rem; color: var(--text-secondary); line-height: 1.7;
  max-height: 400px; overflow-y: auto;
}

@media (max-width: 980px) {
  .sched-grid { grid-template-columns: 1fr; }
  .sched-grid__wide { grid-column: auto; }
  .budget-form,
  .power-row,
  .execution-panel__switch {
    flex-wrap: wrap;
  }
}
</style>

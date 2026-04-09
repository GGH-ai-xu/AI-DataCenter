<script setup>
import { computed, ref, watch } from 'vue'

import GovernancePoliciesWorkspace from '../components/governance/GovernancePoliciesWorkspace.vue'
import UserRulesGrid from '../components/tasks/UserRulesGrid.vue'
import {
  deleteGovernanceRule,
  runScheduleOnce,
  saveGovernanceRule,
  setCarbonBudget,
  setManualPowerLimit,
  setPowerBudget,
  toggleAutoSchedule,
} from '../services/api.js'
import {
  buildDraftCardState,
  buildExecutionBannerModel,
} from '../lib/governancePoliciesConsoleState.js'
import {
  applyBudgetState,
  applyCarbonState,
  formatActionLabel,
  formatActionTarget,
} from '../lib/governancePolicyState.js'
import { buildGovernanceRulesModel } from '../lib/governancePageModels.js'
import { useAppStore } from '../stores/app.js'

const DEFAULT_POWER_BUDGET = 1200
const DEFAULT_CARBON_BUDGET = 50
const BUDGET_TITLE = '总功率预算治理'
const CARBON_TITLE = '碳预算治理'
const ADVANCED_TITLE = '高级策略'

const props = defineProps({
  execution: {
    type: Object,
    default: () => ({}),
  },
  feedback: {
    type: Object,
    default: () => ({}),
  },
  governance: {
    type: Object,
    default: () => ({}),
  },
  reviewModel: {
    type: Object,
    default: () => ({}),
  },
})

const store = useAppStore()
const budget = ref(applyBudgetState())
const carbonBudget = ref(applyCarbonState())
const budgetDraft = ref(createBudgetDraft())
const carbonDraft = ref(createCarbonDraft())
const powerInputs = ref({})
const scheduleResult = ref(null)
const showAdvanced = ref(false)

const policiesState = computed(() => props.governance.policiesState || {})
const autoEnabled = computed(() => Boolean(policiesState.value.scheduler?.auto_enabled))
const budgetCardState = computed(() => buildDraftCardState({
  kind: 'budget',
  current: budget.value,
  draft: budgetDraft.value,
}))
const carbonCardState = computed(() => buildDraftCardState({
  kind: 'carbon',
  current: carbonBudget.value,
  draft: carbonDraft.value,
}))
const executionReady = computed(() => Boolean(props.execution.isReal && props.execution.riskAcknowledged))
const executionBanner = computed(() => buildExecutionBannerModel({
  actionLabel: '执行一次调度',
  isReal: props.execution.isReal,
  riskAcknowledged: props.execution.riskAcknowledged,
  reversible: true,
}))
const rulesModel = computed(() => buildGovernanceRulesModel({
  users: policiesState.value.fairness?.users || [],
  rules: policiesState.value.rules || [],
}))
const gpuTargets = computed(() => {
  if (store.gpus.length) {
    return store.gpus.map((gpu) => gpu.index)
  }
  const managedCount = Number(budget.value.managed_gpu_count || 0)
  return Array.from({ length: managedCount }, (_, index) => index)
})

const handlers = {
  saveBudget,
  saveCarbon,
  toggleAuto,
  runOnce,
  updateRiskAcknowledged,
  setPower,
  saveRule,
  resetRule,
}

watch(policiesState, syncPolicyState, { immediate: true, deep: true })

function createBudgetDraft(source = {}) {
  return {
    enabled: Boolean(source.enabled),
    total_power_budget: Number(source.total_power_budget || DEFAULT_POWER_BUDGET),
  }
}

function createCarbonDraft(source = {}) {
  return {
    enabled: Boolean(source.enabled),
    daily_budget_kg: Number(source.daily_budget_kg || DEFAULT_CARBON_BUDGET),
  }
}

function shouldKeepDraft(kind, current, draft) {
  return buildDraftCardState({ kind, current, draft }).pending
}

function syncPolicyState(next) {
  const nextBudget = applyBudgetState(next.scheduler?.budget)
  const keepBudgetDraft = shouldKeepDraft('budget', budget.value, budgetDraft.value)
  budget.value = nextBudget
  if (!keepBudgetDraft) {
    budgetDraft.value = createBudgetDraft(nextBudget)
  }

  const nextCarbon = applyCarbonState(carbonBudget.value, next.carbon)
  const keepCarbonDraft = shouldKeepDraft('carbon', carbonBudget.value, carbonDraft.value)
  carbonBudget.value = nextCarbon
  if (!keepCarbonDraft) {
    carbonDraft.value = createCarbonDraft(nextCarbon)
  }
}

function showNotice(tone, title, detail) {
  props.feedback.showNotice?.(tone, title, detail)
}

async function refreshPolicies() {
  await props.governance.refreshPolicies?.({ force: true })
}

async function refreshReview() {
  await props.governance.refreshReview?.({ force: true })
}

function ensureRiskAcknowledged(label) {
  if (!props.execution.isReal) {
    showNotice('warning', '当前仅支持真实执行', `${label}仅支持真实执行，请先确认风险。`)
    return false
  }
  if (props.execution.riskAcknowledged) return true
  showNotice('warning', '尚未确认风险', `${label}前请先勾选风险确认。`)
  return false
}

function updateRiskAcknowledged(value) {
  props.execution.riskAcknowledged = value
}

async function saveBudget() {
  const limit = Number(budgetDraft.value.total_power_budget)
  const { data } = await setPowerBudget(Boolean(budgetDraft.value.enabled), limit)
  budget.value = applyBudgetState(data.budget)
  budgetDraft.value = createBudgetDraft(budget.value)
  showNotice('ok', '预算已更新', `总功率预算已设置为 ${budget.value.total_power_budget}W。`)
  await refreshPolicies()
}

async function saveCarbon() {
  const amount = Number(carbonDraft.value.daily_budget_kg)
  const { data } = await setCarbonBudget(Boolean(carbonDraft.value.enabled), amount)
  carbonBudget.value = applyCarbonState(carbonBudget.value, data.carbon_budget)
  carbonDraft.value = createCarbonDraft(carbonBudget.value)
  showNotice('ok', '碳预算已更新', `每日碳预算已设置为 ${carbonBudget.value.daily_budget_kg} kgCO2。`)
  await refreshPolicies()
}

async function toggleAuto() {
  const next = !autoEnabled.value
  await toggleAutoSchedule(next)
  showNotice('ok', '自动调度已更新', next ? '自动调度已开启。' : '自动调度已关闭。')
  await refreshPolicies()
}

async function setPower(gpuIndex) {
  const value = Number(powerInputs.value[gpuIndex])
  if (!ensureRiskAcknowledged('单卡限功率')) return
  if (props.execution.isReal && !window.confirm(`将把 GPU ${gpuIndex} 的功耗上限设为 ${value}W，是否继续？`)) {
    return
  }
  try {
    await setManualPowerLimit(gpuIndex, value, props.execution.buildExecutionParams?.())
  } catch (error) {
    console.error(error)
    showNotice('critical', '单卡功耗写入失败', error?.response?.data?.detail || error?.message || '请稍后重试。')
    return
  }
  showNotice('ok', '单卡功耗已写入', `GPU ${gpuIndex} 目标功耗上限 ${value}W。`)
  await refreshPolicies()
}

async function runOnce() {
  if (!ensureRiskAcknowledged('调度执行')) return
  if (props.execution.isReal && !window.confirm('将执行真实调度动作，是否继续？')) {
    return
  }
  let data = null
  try {
    ({ data } = await runScheduleOnce(props.execution.buildExecutionParams?.()))
  } catch (error) {
    console.error(error)
    showNotice('critical', '调度执行失败', error?.response?.data?.detail || error?.message || '请稍后重试。')
    return
  }
  if (data?.error) {
    showNotice('warning', '调度未执行', data.error)
    return
  }
  scheduleResult.value = data
  showNotice('ok', '调度已执行', '本次调度已完成，详细结果请到治理复盘查看。')
  await refreshPolicies()
  await refreshReview()
}

async function saveRule(payload) {
  await saveGovernanceRule(payload)
  showNotice('ok', '高级策略已更新', `用户 ${payload.username} 的规则已保存。`)
  await refreshPolicies()
}

async function resetRule(username) {
  await deleteGovernanceRule(username)
  showNotice('ok', '高级策略已重置', `用户 ${username} 的规则已恢复默认。`)
  await refreshPolicies()
}
</script>

<template>
  <GovernancePoliciesWorkspace
    :budget-title="BUDGET_TITLE"
    :carbon-title="CARBON_TITLE"
    :advanced-title="ADVANCED_TITLE"
    :budget="budget"
    :budget-draft="budgetDraft"
    :budget-card-state="budgetCardState"
    :carbon-budget="carbonBudget"
    :carbon-draft="carbonDraft"
    :carbon-card-state="carbonCardState"
    :auto-enabled="autoEnabled"
    :execution-banner="executionBanner"
    :execution-ready="executionReady"
    :risk-acknowledged="props.execution.riskAcknowledged"
    :schedule-result="scheduleResult"
    :show-advanced="showAdvanced"
    :rules-users="rulesModel.users"
    :gpu-targets="gpuTargets"
    :power-inputs="powerInputs"
    :user-rules-component="UserRulesGrid"
    :format-action-label="formatActionLabel"
    :format-action-target="formatActionTarget"
    :handlers="handlers"
    @toggle-advanced="showAdvanced = !showAdvanced"
  />
</template>

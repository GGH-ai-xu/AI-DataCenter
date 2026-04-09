import { computed, ref } from 'vue'

/**
 * 治理工作区执行确认 composable
 * 当前只支持真实执行，所有动作都要求显式风险确认
 */
export function useExecutionMode() {
  const executionMode = ref('real')
  const riskAcknowledged = ref(false)

  const isDryRun = computed(() => false)
  const isReal = computed(() => true)
  const canExecute = computed(() => riskAcknowledged.value)

  const modeLabel = computed(() => '真实执行')
  const modeBadgeClass = computed(() => 'status-badge--warning')

  /** 构建传给后端的风险确认参数 */
  function buildExecutionParams() {
    return {
      acknowledge_risk: riskAcknowledged.value,
    }
  }

  return {
    executionMode,
    riskAcknowledged,
    isDryRun,
    isReal,
    canExecute,
    modeLabel,
    modeBadgeClass,
    buildExecutionParams,
  }
}

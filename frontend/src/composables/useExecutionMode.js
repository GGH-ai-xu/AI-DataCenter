import { computed, ref } from 'vue'

/**
 * 执行模式管理 composable
 * 在 TaskManager / Scheduler 等页面共享演练/真实执行逻辑
 */
export function useExecutionMode() {
  const executionMode = ref('dry_run')
  const riskAcknowledged = ref(false)

  const isDryRun = computed(() => executionMode.value === 'dry_run')
  const isReal = computed(() => executionMode.value === 'real')
  const canExecute = computed(() => isDryRun.value || riskAcknowledged.value)

  const modeLabel = computed(() => isReal.value ? '真实执行' : '演练模式')
  const modeBadgeClass = computed(() => isReal.value ? 'status-badge--warning' : 'status-badge--ok')

  /** 构建传给后端的 dry_run / acknowledge_risk 参数 */
  function buildExecutionParams() {
    return {
      dry_run: isDryRun.value,
      acknowledge_risk: isReal.value && riskAcknowledged.value,
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

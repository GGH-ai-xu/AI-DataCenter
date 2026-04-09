export function createGovernanceLoaders(api) {
  return {
    async loadActionsBundle() {
      const [{ data: taskData }, { data: fairnessData }] = await Promise.all([
        api.getTasks(),
        api.getFairnessGovernance(),
      ])
      return {
        processes: taskData?.processes || [],
        fairness: fairnessData || {},
      }
    },

    async loadPoliciesBundle() {
      const [
        { data: schedulerData },
        { data: carbonData },
        { data: fairnessData },
        { data: rulesData },
      ] = await Promise.all([
        api.getSchedulerStatus(),
        api.getCarbonBudget(),
        api.getFairnessGovernance(),
        api.getGovernanceRules(),
      ])
      return {
        scheduler: schedulerData || {},
        carbon: carbonData || {},
        fairness: fairnessData || {},
        rules: rulesData?.rules || [],
      }
    },

    async loadReviewBundle() {
      const [{ data: auditData }, { data: evaluationData }] = await Promise.all([
        api.getAuditLogs(100, 72),
        api.getScheduleEvaluation(),
      ])
      return {
        auditLogs: auditData?.logs || [],
        evaluation: evaluationData || null,
      }
    },
  }
}

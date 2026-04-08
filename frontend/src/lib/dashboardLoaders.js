export function createDashboardLoaders(api) {
  return {
    async loadOverviewBundle() {
      const [{ data: scheduler }, { data: health }, { data: fairness }] = await Promise.all([
        api.getSchedulerStatus(),
        api.healthCheck(),
        api.getFairnessGovernance(),
      ])
      return { scheduler, health, fairness }
    },
    async loadHealthBundle() {
      const [{ data: health }, { data: selfCheck }] = await Promise.all([
        api.healthCheck(),
        api.getSystemSelfCheck(),
      ])
      return { health, selfCheck }
    },
  }
}

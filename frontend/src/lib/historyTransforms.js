export function appendGpuHistorySample(history = {}, gpus = [], timestamp = new Date(), maxPoints = 60) {
  const nextHistory = { ...history }

  for (const gpu of gpus) {
    const nextPoints = [...(nextHistory[gpu.index] || []), {
      time: timestamp,
      value: gpu.power_usage,
    }]
    nextHistory[gpu.index] = nextPoints.slice(-maxPoints)
  }

  return nextHistory
}

export function buildGpuDetailSeries(history = []) {
  const series = {
    times: [],
    temperatures: [],
    powerUsage: [],
    gpuUtilization: [],
    memoryUtilization: [],
  }

  for (const point of history) {
    series.times.push(new Date(point.timestamp * 1000))
    series.temperatures.push(point.temperature)
    series.powerUsage.push(point.power_usage)
    series.gpuUtilization.push(point.gpu_utilization)
    series.memoryUtilization.push(point.memory_utilization)
  }

  return series
}

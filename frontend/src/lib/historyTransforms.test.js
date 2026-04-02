import test from 'node:test'
import assert from 'node:assert/strict'
import {
  appendGpuHistorySample,
  buildGpuDetailSeries,
} from './historyTransforms.js'

test('appendGpuHistorySample keeps only the latest points per gpu', () => {
  const history = appendGpuHistorySample(
    {},
    [{ index: 0, power_usage: 100 }],
    new Date('2026-04-01T00:00:00Z'),
    2,
  )
  const nextHistory = appendGpuHistorySample(
    history,
    [{ index: 0, power_usage: 110 }],
    new Date('2026-04-01T00:01:00Z'),
    2,
  )
  const finalHistory = appendGpuHistorySample(
    nextHistory,
    [{ index: 0, power_usage: 120 }],
    new Date('2026-04-01T00:02:00Z'),
    2,
  )

  assert.deepEqual(finalHistory[0].map((point) => point.value), [110, 120])
})

test('buildGpuDetailSeries walks the history array once', () => {
  const series = buildGpuDetailSeries([
    {
      timestamp: 1,
      temperature: 70,
      power_usage: 200,
      gpu_utilization: 80,
      memory_utilization: 60,
    },
  ])

  assert.equal(series.times.length, 1)
  assert.equal(series.temperatures[0], 70)
  assert.equal(series.powerUsage[0], 200)
})

import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildDashboardHealthModel,
  buildDashboardOverviewModel,
} from './dashboardPageModels.js'

test('buildDashboardOverviewModel returns summary, routes, and signal cards', () => {
  const model = buildDashboardOverviewModel({
    importedIndexes: [1, 2, 3],
    sourceMode: 'remote',
    workspaceReady: true,
    wsConnected: true,
    processCount: 5,
    budget: {
      is_exceeded: true,
      usage_pct: 112,
    },
    fairnessOverview: {
      level: 'watch',
      active_users: 2,
      highest_share_pct: 67,
    },
    criticalAlertCount: 2,
  })

  assert.equal(model.quickStats.length, 4)
  assert.equal(model.routeCards.length, 4)
  assert.equal(model.signalCards.length, 3)
  assert.equal(model.quickStats[0].label, '导入范围')
  assert.equal(model.signalCards[0].tone, 'critical')
  assert.match(model.summaryLine, /预算/)
  assert.deepEqual(
    model.routeCards.slice(0, 3).map((item) => item.path),
    ['/governance/actions', '/governance/policies', '/governance/review'],
  )
})

test('buildDashboardHealthModel separates priority and healthy checks', () => {
  const model = buildDashboardHealthModel({
    importedLabel: '已导入 3 张卡',
    wsConnected: false,
    selfCheck: {
      summary: {
        title: '2 项异常',
        message: '其中 1 项影响实时采集',
      },
      checks: [
        { key: 'gpu-agent', label: 'GPU Agent', status: 'critical', detail: '实时采集失败' },
        { key: 'ws', label: 'WebSocket', status: 'warning', detail: '连接断开' },
        { key: 'llm', label: 'AI 助手', status: 'ok', detail: '正常' },
      ],
      ws_connections: 0,
      llm_available: true,
    },
  })

  assert.equal(model.factCards.length, 4)
  assert.deepEqual(
    model.priorityChecks.map((item) => item.key),
    ['gpu-agent', 'ws'],
  )
  assert.deepEqual(
    model.healthyChecks.map((item) => item.key),
    ['llm'],
  )
})

test('buildDashboardHealthModel exposes board metadata for the B2 health card', () => {
  const waitingModel = buildDashboardHealthModel({
    importedLabel: '未导入 GPU',
    wsConnected: false,
    selfCheck: {},
  })

  assert.equal(waitingModel.healthProgressLabel, '等待巡检')
  assert.equal(waitingModel.totalCheckCount, 0)
  assert.equal(waitingModel.healthyCheckCount, 0)
  assert.equal(waitingModel.primaryCheck, null)
  assert.equal(waitingModel.remainingPriorityCount, 0)
  assert.equal(waitingModel.hasChecks, false)

  const model = buildDashboardHealthModel({
    importedLabel: '已导入 3 张卡',
    wsConnected: false,
    selfCheck: {
      summary: {
        title: '2 项异常',
        message: '其中 1 项影响实时采集',
      },
      checks: [
        { key: 'gpu-agent', label: 'GPU Agent', status: 'critical', detail: '实时采集失败' },
        { key: 'ws', label: 'WebSocket', status: 'warning', detail: '连接断开' },
        { key: 'llm', label: 'AI 助手', status: 'ok', detail: '正常' },
      ],
      ws_connections: 0,
      llm_available: false,
    },
  })

  assert.equal(model.healthProgressLabel, '健康 1 / 3')
  assert.equal(model.totalCheckCount, 3)
  assert.equal(model.healthyCheckCount, 1)
  assert.equal(model.primaryCheck?.key, 'gpu-agent')
  assert.equal(model.remainingPriorityCount, 1)
  assert.equal(model.hasChecks, true)
  assert.equal(model.factCards[1].tone, 'warning')
  assert.equal(model.factCards[2].tone, 'warning')
  assert.equal(model.factCards[3].tone, 'warning')
})

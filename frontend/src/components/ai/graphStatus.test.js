import test from 'node:test'
import assert from 'node:assert/strict'

import {
  getGraphConnectionStatus,
  getGraphExecuteDisabledReason,
  getGraphGenerateDisabledReason,
  getGraphRecoveryHint,
} from './graphStatus.js'


test('getGraphConnectionStatus returns expected label for each connection state', () => {
  assert.equal(getGraphConnectionStatus({ configured: false }), '未配置')
  assert.equal(getGraphConnectionStatus({ configured: true, dependency_installed: false }), '缺少驱动')
  assert.equal(
    getGraphConnectionStatus({
      configured: true,
      dependency_installed: true,
      neo4j_connected: false,
    }),
    '未连接',
  )
  assert.equal(
    getGraphConnectionStatus({
      configured: true,
      dependency_installed: true,
      neo4j_connected: true,
    }),
    '可写入',
  )
})


test('getGraphGenerateDisabledReason explains missing llm or paper content', () => {
  assert.match(
    getGraphGenerateDisabledReason({
      llmReady: false,
      form: { title: 'GraphRAG', abstract: 'abstract', content: '' },
    }),
    /LLM 未就绪/,
  )
  assert.match(
    getGraphGenerateDisabledReason({
      llmReady: true,
      form: { title: '', abstract: 'abstract', content: '' },
    }),
    /填写标题/,
  )
  assert.match(
    getGraphGenerateDisabledReason({
      llmReady: true,
      form: { title: 'GraphRAG', abstract: '', content: '' },
    }),
    /至少提供摘要或正文片段/,
  )
  assert.equal(
    getGraphGenerateDisabledReason({
      llmReady: true,
      form: { title: 'GraphRAG', abstract: 'abstract', content: '' },
    }),
    '',
  )
})


test('getGraphExecuteDisabledReason explains missing draft or neo4j connection', () => {
  assert.match(
    getGraphExecuteDisabledReason({
      draftResult: null,
      summary: { neo4j_connected: false },
    }),
    /先生成图谱草稿/,
  )
  assert.match(
    getGraphExecuteDisabledReason({
      draftResult: { graph: { nodes: [{ id: 'paper_1' }] } },
      summary: { neo4j_connected: false, message: 'Could not connect to 127.0.0.1:7687' },
    }),
    /127\.0\.0\.1:7687/,
  )
  assert.equal(
    getGraphExecuteDisabledReason({
      draftResult: { graph: { nodes: [{ id: 'paper_1' }] } },
      summary: { neo4j_connected: true },
    }),
    '',
  )
})


test('getGraphRecoveryHint prefers local bootstrap guidance when available', () => {
  assert.match(
    getGraphRecoveryHint({
      neo4j_connected: false,
      local_start_available: true,
      local_start_message: '可尝试一键启动或重连本地 Neo4j（127.0.0.1:7687）。',
    }),
    /一键启动/,
  )
  assert.match(
    getGraphRecoveryHint({
      neo4j_connected: false,
      local_start_available: false,
      local_start_message: '当前 Neo4j 不是本机实例，无法自动启动远程图库。',
    }),
    /远程图库/,
  )
})

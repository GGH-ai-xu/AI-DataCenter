import test from 'node:test'
import assert from 'node:assert/strict'
import {
  formatImportSourceLabel,
  formatImportedGpuLabel,
  hasValidImportContext,
} from './importContext.js'

test('hasValidImportContext requires valid flag and selected gpu indexes', () => {
  assert.equal(hasValidImportContext(null), false)
  assert.equal(hasValidImportContext({ valid: true, imported_gpu_indexes: [] }), false)
  assert.equal(hasValidImportContext({ valid: false, imported_gpu_indexes: [0] }), false)
  assert.equal(hasValidImportContext({ valid: true, imported_gpu_indexes: [0, 2] }), true)
})

test('formatImportedGpuLabel summarizes imported gpu count', () => {
  assert.equal(formatImportedGpuLabel([]), '未导入 GPU')
  assert.equal(formatImportedGpuLabel([1]), '已导入 1 张卡')
  assert.equal(formatImportedGpuLabel([0, 2]), '已导入 2 张卡')
})

test('formatImportSourceLabel maps provider type to display copy', () => {
  assert.equal(formatImportSourceLabel({ provider_type: 'ssh_linux' }), 'SSH Linux 导入模式')
  assert.equal(formatImportSourceLabel({ provider_type: 'http_remote' }), '远程 Agent 导入模式')
  assert.equal(formatImportSourceLabel({ provider_type: 'http_local' }), '本机 Agent 导入模式')
  assert.equal(formatImportSourceLabel({}), '导入模式待识别')
})

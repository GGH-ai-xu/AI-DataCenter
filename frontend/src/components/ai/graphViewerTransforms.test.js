import test from 'node:test'
import assert from 'node:assert/strict'

import { buildGraphDefenseOverview, buildGraphViewerOption } from './graphViewerTransforms.js'


test('buildGraphViewerOption maps graph nodes and relationships into echarts graph data', () => {
  const option = buildGraphViewerOption({
    nodes: [
      { id: '1', label: 'Paper', name: 'Self-RAG', description: 'paper' },
      { id: '2', label: 'Method', name: 'Retrieval-Augmented Generation (RAG)', description: 'method' },
    ],
    relationships: [
      { id: 'r1', source_id: '1', target_id: '2', type: 'PROPOSES', description: 'paper proposes method' },
    ],
  }, '1')

  assert.equal(option.series[0].type, 'graph')
  assert.equal(option.series[0].data.length, 2)
  assert.equal(option.series[0].links.length, 1)
  assert.equal(option.series[0].data[0].id, '1')
  assert.equal(option.series[0].data[0].symbolSize > option.series[0].data[1].symbolSize, true)
  assert.equal(option.series[0].links[0].source, '1')
  assert.equal(option.series[0].links[0].target, '2')
  assert.equal(option.series[0].links[0].lineStyle.width, 3.1)
})


test('buildGraphDefenseOverview summarizes answer-ready talking points', () => {
  const overview = buildGraphDefenseOverview({
    nodes: [
      { id: '1', label: 'Paper', name: 'Self-RAG', paper_title: 'Self-RAG' },
      { id: '2', label: 'Method', name: 'Self-RAG (Method)', paper_title: 'Self-RAG' },
      { id: '3', label: 'Task', name: 'Open-Domain QA', paper_title: 'Self-RAG' },
    ],
    relationships: [
      { id: 'r1', source_id: '1', target_id: '2', type: 'PROPOSES' },
      { id: 'r2', source_id: '2', target_id: '3', type: 'SOLVES' },
    ],
  })

  assert.match(overview.headline, /1 篇论文/)
  assert.equal(overview.focusCards.length, 4)
  assert.equal(overview.talkingPoints.length >= 3, true)
  assert.equal(overview.judgeQuestions.length >= 3, true)
  assert.equal(overview.presentationFlow.length, 4)
  assert.equal(overview.answerReadyNotes.length, 3)
})

import test from 'node:test'
import assert from 'node:assert/strict'
import { proxyRefs } from 'vue'

import {
  resetGraphWorkspaceDependencies,
  setGraphWorkspaceDependencies,
  useGraphWorkspace,
} from './useGraphWorkspace.js'


test('useGraphWorkspace generates draft and executes import', async () => {
  const calls = {
    draft: 0,
    execute: 0,
    summary: 0,
  }
  setGraphWorkspaceDependencies({
    getGraphSummaryApi: async () => {
      calls.summary += 1
      return {
        data: {
          ready: true,
          configured: true,
          dependency_installed: true,
          neo4j_connected: true,
          database: 'neo4j',
          paper_count: 2,
          node_count: 3,
          relation_count: 2,
          message: 'Neo4j 已就绪',
        },
      }
    },
    graphDraftApi: async () => {
      calls.draft += 1
      return {
        data: {
          graph: {
            title: 'GraphRAG',
            source: 'paper',
            nodes: [
              { id: 'paper_1', label: 'Paper', name: 'GraphRAG' },
              { id: 'method_1', label: 'Method', name: 'GraphRAG Method', paper_title: 'GraphRAG' },
            ],
            relations: [
              { from_id: 'paper_1', to_id: 'method_1', type: 'PROPOSES' },
            ],
          },
          summary: {
            title: 'GraphRAG',
            node_count: 2,
            relation_count: 1,
            labels: { Paper: 1, Method: 1 },
          },
          cypher: 'MERGE (...)',
          warnings: [],
        },
      }
    },
    graphExecuteApi: async () => {
      calls.execute += 1
      return {
        data: {
          ok: true,
          message: '图谱写入成功',
          nodes_created: 2,
          relationships_created: 1,
          properties_set: 4,
          graph_summary: {
            ready: true,
            configured: true,
            dependency_installed: true,
            neo4j_connected: true,
            database: 'neo4j',
            paper_count: 3,
            node_count: 5,
            relation_count: 3,
            message: 'Neo4j 已就绪',
          },
        },
      }
    },
    getGraphViewApi: async () => ({
      data: {
        nodes: [
          { id: 'paper_1', label: 'Paper', name: 'GraphRAG' },
          { id: 'method_1', label: 'Method', name: 'GraphRAG Method' },
        ],
        relationships: [
          { id: 'rel_1', source_id: 'paper_1', target_id: 'method_1', type: 'PROPOSES' },
        ],
        label_counts: { Paper: 1, Method: 1 },
        relation_type_counts: { PROPOSES: 1 },
      },
    }),
    reconnectGraphApi: async () => ({
      data: {
        success: true,
        message: 'Neo4j 已完成重连。',
        graph_summary: {
          ready: true,
          configured: true,
          dependency_installed: true,
          neo4j_connected: true,
          database: 'neo4j',
          paper_count: 3,
          node_count: 5,
          relation_count: 3,
          message: 'Neo4j 已就绪',
        },
      },
    }),
  })

  const workspace = useGraphWorkspace()
  workspace.form.value.title = 'GraphRAG'
  workspace.form.value.abstract = 'A knowledge graph retrieval paper.'

  await workspace.refreshSummary()
  assert.equal(workspace.summary.value.paper_count, 2)
  assert.equal(workspace.summary.value.node_count, 3)

  await workspace.generateDraft()
  assert.equal(calls.draft, 1)
  assert.equal(workspace.draftResult.value.summary.node_count, 2)
  assert.equal(workspace.canExecute.value, true)

  await workspace.executeImport()
  assert.equal(calls.execute, 1)
  assert.equal(workspace.executionResult.value.nodes_created, 2)
  assert.equal(workspace.summary.value.paper_count, 3)
  assert.equal(workspace.summary.value.node_count, 5)

  resetGraphWorkspaceDependencies()
})


test('useGraphWorkspace surfaces draft errors', async () => {
  setGraphWorkspaceDependencies({
    getGraphSummaryApi: async () => ({ data: {} }),
    graphDraftApi: async () => {
      throw new Error('draft failed')
    },
    getGraphViewApi: async () => ({ data: { nodes: [], relationships: [] } }),
    graphExecuteApi: async () => ({ data: {} }),
    reconnectGraphApi: async () => ({ data: {} }),
  })

  const workspace = useGraphWorkspace()
  workspace.form.value.title = 'Bad draft'
  workspace.form.value.content = 'Noisy content'

  const result = await workspace.generateDraft()
  assert.equal(result, null)
  assert.match(workspace.feedback.value.text, /draft failed/)

  resetGraphWorkspaceDependencies()
})


test('useGraphWorkspace reports refresh progress result for manual refresh', async () => {
  setGraphWorkspaceDependencies({
    getGraphSummaryApi: async () => ({
      data: {
        ready: true,
        configured: true,
        dependency_installed: true,
        neo4j_connected: true,
        database: 'neo4j',
        paper_count: 3,
        node_count: 19,
        relation_count: 21,
        message: 'Neo4j 已就绪',
      },
    }),
    getGraphViewApi: async () => ({ data: { nodes: [], relationships: [] } }),
    graphDraftApi: async () => ({ data: {} }),
    graphExecuteApi: async () => ({ data: {} }),
    reconnectGraphApi: async () => ({ data: {} }),
  })

  const workspace = useGraphWorkspace()
  assert.equal(workspace.refreshBusy.value, false)

  await workspace.refreshSummary()

  assert.equal(workspace.refreshBusy.value, false)
  assert.equal(workspace.summary.value.paper_count, 3)
  assert.equal(workspace.summary.value.node_count, 19)
  assert.match(workspace.feedback.value.text, /已刷新/)

  resetGraphWorkspaceDependencies()
})


test('useGraphWorkspace blocks execute while draft generation is still running', async () => {
  let resolveDraft
  const draftPromise = new Promise((resolve) => {
    resolveDraft = resolve
  })
  const calls = {
    draft: 0,
    execute: 0,
  }

  setGraphWorkspaceDependencies({
    getGraphSummaryApi: async () => ({
      data: {
        ready: true,
        configured: true,
        dependency_installed: true,
        neo4j_connected: true,
        database: 'neo4j',
      },
    }),
    graphDraftApi: async () => {
      calls.draft += 1
      await draftPromise
      return {
        data: {
          graph: {
            title: 'GraphRAG',
            source: 'paper',
            nodes: [
              { id: 'paper_1', label: 'Paper', name: 'GraphRAG' },
            ],
            relations: [],
          },
          summary: {
            title: 'GraphRAG',
            node_count: 1,
            relation_count: 0,
          },
          cypher: 'MERGE (...)',
          warnings: [],
        },
      }
    },
    graphExecuteApi: async () => {
      calls.execute += 1
      return { data: {} }
    },
    getGraphViewApi: async () => ({ data: { nodes: [], relationships: [] } }),
    reconnectGraphApi: async () => ({ data: {} }),
  })

  const workspace = useGraphWorkspace()
  workspace.form.value.title = 'GraphRAG'
  workspace.form.value.abstract = 'A knowledge graph retrieval paper.'
  workspace.draftResult.value = {
    graph: {
      title: 'Old GraphRAG',
      source: 'paper',
      nodes: [{ id: 'paper_1', label: 'Paper', name: 'Old GraphRAG' }],
      relations: [],
    },
  }
  workspace.summary.value.neo4j_connected = true

  const pendingDraft = workspace.generateDraft()
  assert.equal(workspace.draftBusy.value, true)

  const executeResult = await workspace.executeImport()
  assert.equal(executeResult, null)
  assert.equal(calls.execute, 0)
  assert.equal(workspace.executeBusy.value, false)

  resolveDraft()
  await pendingDraft
  assert.equal(calls.draft, 1)

  resetGraphWorkspaceDependencies()
})


test('useGraphWorkspace resets draft busy state when request times out', async () => {
  setGraphWorkspaceDependencies({
    requestTimeoutMs: 20,
    getGraphSummaryApi: async () => ({ data: {} }),
    graphDraftApi: async () => new Promise(() => {}),
    getGraphViewApi: async () => ({ data: { nodes: [], relationships: [] } }),
    graphExecuteApi: async () => ({ data: {} }),
    reconnectGraphApi: async () => ({ data: {} }),
  })

  const workspace = useGraphWorkspace()
  workspace.form.value.title = 'GraphRAG'
  workspace.form.value.abstract = 'A knowledge graph retrieval paper.'

  const result = await workspace.generateDraft()
  assert.equal(result, null)
  assert.equal(workspace.draftBusy.value, false)
  assert.match(workspace.feedback.value.text, /超时/)

  resetGraphWorkspaceDependencies()
})


test('proxyRefs exposes graph workspace state as plain values for view bindings', async () => {
  setGraphWorkspaceDependencies({
    getGraphSummaryApi: async () => ({
      data: {
        ready: true,
        configured: true,
        dependency_installed: true,
        neo4j_connected: true,
        database: 'neo4j',
        paper_count: 3,
        node_count: 19,
        relation_count: 21,
        message: 'Neo4j 已就绪',
      },
    }),
    graphDraftApi: async () => ({
      data: {
        graph: {
          title: 'GraphRAG',
          source: 'paper',
          nodes: [{ id: 'paper_1', label: 'Paper', name: 'GraphRAG' }],
          relations: [],
        },
        summary: {
          title: 'GraphRAG',
          node_count: 1,
          relation_count: 0,
          labels: { Paper: 1 },
        },
        cypher: 'MERGE (...)',
        warnings: [],
      },
    }),
    graphExecuteApi: async () => ({
      data: {
        ok: true,
      },
    }),
    getGraphViewApi: async () => ({ data: { nodes: [], relationships: [] } }),
    reconnectGraphApi: async () => ({ data: {} }),
  })

  const workspace = useGraphWorkspace()
  const exposed = proxyRefs(workspace)

  assert.equal(exposed.refreshBusy, false)
  assert.equal(exposed.draftBusy, false)
  assert.equal(exposed.executeBusy, false)
  assert.equal(exposed.reconnectBusy, false)
  assert.equal(exposed.viewBusy, false)
  assert.equal(exposed.expandBusy, false)
  assert.equal(exposed.canGenerate, false)
  assert.equal(exposed.form.title, '')
  assert.equal(exposed.graphFilters.query, '')

  workspace.form.value.title = 'GraphRAG'
  workspace.form.value.abstract = 'A knowledge graph retrieval paper.'
  await workspace.refreshSummary()

  assert.equal(exposed.canGenerate, true)
  assert.equal(exposed.summary.neo4j_connected, true)
  assert.equal(exposed.summary.paper_count, 3)
  assert.equal(exposed.summary.node_count, 19)
  assert.equal(exposed.summary.message, 'Neo4j 已就绪')

  resetGraphWorkspaceDependencies()
})


test('useGraphWorkspace can recover local neo4j connection and refresh summary', async () => {
  let reconnectCalls = 0

  setGraphWorkspaceDependencies({
    getGraphSummaryApi: async () => ({
      data: {
        ready: false,
        configured: true,
        dependency_installed: true,
        neo4j_connected: false,
        database: 'neo4j',
        paper_count: 0,
        node_count: 0,
        relation_count: 0,
        local_start_available: true,
        local_start_message: '可尝试一键启动或重连本地 Neo4j（127.0.0.1:7687）。',
        message: 'Could not connect to 127.0.0.1:7687',
      },
    }),
    graphDraftApi: async () => ({ data: {} }),
    getGraphViewApi: async () => ({
      data: {
        nodes: [
          { id: 'paper_1', label: 'Paper', name: 'Self-RAG' },
        ],
        relationships: [],
        label_counts: { Paper: 1 },
        relation_type_counts: {},
      },
    }),
    graphExecuteApi: async () => ({ data: {} }),
    reconnectGraphApi: async () => {
      reconnectCalls += 1
      return {
        data: {
          success: true,
          started: true,
          message: '本地 Neo4j 已启动并连接。',
          graph_summary: {
            ready: true,
            configured: true,
            dependency_installed: true,
            neo4j_connected: true,
            database: 'neo4j',
            paper_count: 4,
            node_count: 22,
            relation_count: 25,
            local_start_available: true,
            local_start_message: '可尝试一键启动或重连本地 Neo4j（127.0.0.1:7687）。',
            message: 'Neo4j 已就绪',
          },
        },
      }
    },
  })

  const workspace = useGraphWorkspace()
  await workspace.refreshSummary()
  assert.equal(workspace.summary.value.neo4j_connected, false)

  const result = await workspace.recoverConnection()

  assert.equal(reconnectCalls, 1)
  assert.equal(result.message, '本地 Neo4j 已启动并连接。')
  assert.equal(workspace.reconnectBusy.value, false)
  assert.equal(workspace.summary.value.neo4j_connected, true)
  assert.equal(workspace.summary.value.node_count, 22)
  assert.match(workspace.feedback.value.text, /已启动并连接/)

  resetGraphWorkspaceDependencies()
})


test('useGraphWorkspace loads graph view and keeps selected node in sync', async () => {
  setGraphWorkspaceDependencies({
    getGraphSummaryApi: async () => ({ data: {} }),
    getGraphViewApi: async () => ({
      data: {
        query: 'rag',
        limit: 40,
        nodes: [
          { id: 'paper_1', label: 'Paper', name: 'Self-RAG' },
          { id: 'method_1', label: 'Method', name: 'Self-RAG (Method)' },
        ],
        relationships: [
          { id: 'rel_1', source_id: 'paper_1', target_id: 'method_1', type: 'PROPOSES' },
        ],
        label_counts: { Paper: 1, Method: 1 },
        relation_type_counts: { PROPOSES: 1 },
      },
    }),
    graphDraftApi: async () => ({ data: {} }),
    graphExecuteApi: async () => ({ data: {} }),
    reconnectGraphApi: async () => ({ data: {} }),
  })

  const workspace = useGraphWorkspace()
  workspace.graphFilters.value.query = 'rag'
  workspace.graphFilters.value.limit = 40

  const view = await workspace.refreshGraphView()

  assert.equal(view.nodes.length, 2)
  assert.equal(workspace.graphView.value.relationships.length, 1)
  assert.equal(workspace.selectedGraphNodeId.value, 'paper_1')
  assert.equal(workspace.selectedGraphNode.value.name, 'Self-RAG')

  workspace.selectGraphNode('method_1')
  assert.equal(workspace.selectedGraphNode.value.label, 'Method')

  resetGraphWorkspaceDependencies()
})


test('useGraphWorkspace skips graph view request when neo4j is offline', async () => {
  let viewCalls = 0

  setGraphWorkspaceDependencies({
    getGraphSummaryApi: async () => ({
      data: {
        ready: false,
        configured: true,
        dependency_installed: true,
        neo4j_connected: false,
        database: 'neo4j',
        message: 'Neo4j 当前不可用。',
      },
    }),
    getGraphViewApi: async () => {
      viewCalls += 1
      return {
        data: {
          nodes: [{ id: 'paper_1', label: 'Paper', name: 'Should not load' }],
          relationships: [],
        },
      }
    },
    graphDraftApi: async () => ({ data: {} }),
    graphExecuteApi: async () => ({ data: {} }),
    reconnectGraphApi: async () => ({ data: {} }),
  })

  const workspace = useGraphWorkspace()
  await workspace.refreshSummary({ silent: true })

  const view = await workspace.refreshGraphView()

  assert.equal(viewCalls, 0)
  assert.equal(view.nodes.length, 0)
  assert.equal(view.relationships.length, 0)
  assert.match(view.message, /Neo4j 当前不可用/)
  assert.match(workspace.feedback.value.text, /Neo4j 当前不可用/)

  resetGraphWorkspaceDependencies()
})


test('useGraphWorkspace expands neighbors and merges graph payload without duplicates', async () => {
  let expandCalls = 0

  setGraphWorkspaceDependencies({
    getGraphSummaryApi: async () => ({ data: {} }),
    getGraphViewApi: async () => ({
      data: {
        query: 'rag',
        limit: 40,
        nodes: [
          { id: 'paper_1', label: 'Paper', name: 'Self-RAG', paper_title: 'Self-RAG' },
          { id: 'method_1', label: 'Method', name: 'Self-RAG (Method)', paper_title: 'Self-RAG' },
        ],
        relationships: [
          { id: 'rel_1', source_id: 'paper_1', target_id: 'method_1', type: 'PROPOSES' },
        ],
        label_counts: { Paper: 1, Method: 1 },
        relation_type_counts: { PROPOSES: 1 },
      },
    }),
    getGraphNeighborsApi: async ({ node_id, limit }) => {
      expandCalls += 1
      assert.equal(node_id, 'method_1')
      assert.equal(limit, 24)
      return {
        data: {
          expanded_node_id: 'method_1',
          fetched_neighbor_count: 2,
          nodes: [
            { id: 'method_1', label: 'Method', name: 'Self-RAG (Method)', paper_title: 'Self-RAG' },
            { id: 'task_1', label: 'Task', name: 'Open-domain QA', paper_title: 'Self-RAG' },
            { id: 'dataset_1', label: 'Dataset', name: 'Natural Questions', paper_title: 'Self-RAG' },
          ],
          relationships: [
            { id: 'rel_2', source_id: 'method_1', target_id: 'task_1', type: 'SOLVES' },
            { id: 'rel_3', source_id: 'method_1', target_id: 'dataset_1', type: 'USES' },
          ],
        },
      }
    },
    graphDraftApi: async () => ({ data: {} }),
    graphExecuteApi: async () => ({ data: {} }),
    reconnectGraphApi: async () => ({ data: {} }),
  })

  const workspace = useGraphWorkspace()
  await workspace.refreshGraphView()
  workspace.selectGraphNode('method_1')

  const view = await workspace.expandGraphNode('method_1')

  assert.equal(expandCalls, 1)
  assert.equal(workspace.expandBusy.value, false)
  assert.equal(workspace.selectedGraphNodeId.value, 'method_1')
  assert.equal(view.nodes.length, 4)
  assert.equal(view.relationships.length, 3)
  assert.equal(view.label_counts.Task, 1)
  assert.equal(view.label_counts.Dataset, 1)
  assert.equal(view.relation_type_counts.SOLVES, 1)
  assert.equal(view.relation_type_counts.USES, 1)
  assert.match(workspace.feedback.value.text, /已展开 2 个邻居节点/)

  resetGraphWorkspaceDependencies()
})


test('useGraphWorkspace asks graph qa and exposes matched evidence', async () => {
  let qaCalls = 0

  setGraphWorkspaceDependencies({
    getGraphSummaryApi: async () => ({
      data: {
        ready: true,
        configured: true,
        dependency_installed: true,
        neo4j_connected: true,
        database: 'neo4j',
        paper_count: 3,
        node_count: 19,
        relation_count: 21,
        message: 'Neo4j 已就绪',
      },
    }),
    getGraphViewApi: async () => ({ data: { nodes: [], relationships: [] } }),
    graphDraftApi: async () => ({ data: {} }),
    graphExecuteApi: async () => ({ data: {} }),
    reconnectGraphApi: async () => ({ data: {} }),
    graphQaApi: async ({ question }) => {
      qaCalls += 1
      assert.equal(question, 'Self-RAG 和 RAG 有什么关系？')
      return {
        data: {
          question,
          summary: 'Self-RAG 在图库里通过 USES 关系连接到 RAG。',
          answer: '当前图谱显示 Self-RAG 建立在 RAG 范式之上。',
          confidence: 'high',
          evidence: [
            'Self-RAG (Self-Reflective Retrieval-Augmented Generation) -USES-> Retrieval-Augmented Generation (RAG)',
          ],
          follow_ups: ['Self-RAG 还解决了哪些任务？'],
          used_llm: true,
          matched_node_count: 2,
          matched_relationship_count: 1,
          paper_titles: ['Self-RAG'],
          evidence_nodes: [
            { id: 'method_1', label: 'Method', name: 'Self-RAG (Self-Reflective Retrieval-Augmented Generation)' },
            { id: 'method_2', label: 'Method', name: 'Retrieval-Augmented Generation (RAG)' },
          ],
          evidence_relationships: [
            { id: 'rel_1', source_id: 'method_1', target_id: 'method_2', type: 'USES' },
          ],
        },
      }
    },
  })

  const workspace = useGraphWorkspace()
  workspace.summary.value.neo4j_connected = true
  workspace.qaForm.value.question = 'Self-RAG 和 RAG 有什么关系？'

  const result = await workspace.askGraphQuestion()

  assert.equal(qaCalls, 1)
  assert.equal(workspace.qaBusy.value, false)
  assert.equal(result.confidence, 'high')
  assert.equal(workspace.qaResult.value.matched_node_count, 2)
  assert.equal(workspace.selectedGraphNodeId.value, 'method_1')
  assert.match(workspace.feedback.value.text, /USES/)

  resetGraphWorkspaceDependencies()
})


test('useGraphWorkspace sends optimization metadata when generating draft', async () => {
  let receivedPayload = null

  setGraphWorkspaceDependencies({
    getGraphSummaryApi: async () => ({ data: {} }),
    getGraphViewApi: async () => ({ data: { nodes: [], relationships: [] } }),
    graphExecuteApi: async () => ({ data: {} }),
    reconnectGraphApi: async () => ({ data: {} }),
    graphDraftApi: async (payload) => {
      receivedPayload = payload
      return {
        data: {
          graph: {
            title: payload.title,
            mode: payload.mode,
            source: payload.source,
            source_type: payload.source_type,
            domain_tag: payload.domain_tag,
            scenario: payload.scenario,
            nodes: [
              { id: 'strategy_1', label: 'OptimizationStrategy', name: '高峰限功调度' },
            ],
            relations: [],
          },
          summary: {
            title: payload.title,
            mode: payload.mode,
            node_count: 1,
            relation_count: 0,
          },
          cypher: 'MERGE (...)',
          warnings: [],
        },
      }
    },
  })

  const workspace = useGraphWorkspace()
  workspace.form.value.mode = 'optimization'
  workspace.form.value.title = '高峰限功调度'
  workspace.form.value.abstract = '高峰期压低总功耗，但保护紧急任务。'
  workspace.form.value.sourceType = 'strategy'
  workspace.form.value.domainTag = '智算中心优化'
  workspace.form.value.scenario = '高峰限功'

  await workspace.generateDraft()

  assert.deepEqual(receivedPayload, {
    title: '高峰限功调度',
    abstract: '高峰期压低总功耗，但保护紧急任务。',
    content: '',
    mode: 'optimization',
    source: 'optimization',
    source_type: 'strategy',
    domain_tag: '智算中心优化',
    scenario: '高峰限功',
  })

  resetGraphWorkspaceDependencies()
})


test('useGraphWorkspace rebuilds builtin demo graph and refreshes graph view', async () => {
  let rebuildKind = ''
  let viewCalls = 0

  setGraphWorkspaceDependencies({
    getGraphSummaryApi: async () => ({
      data: {
        ready: true,
        configured: true,
        dependency_installed: true,
        neo4j_connected: true,
        database: 'neo4j',
        paper_count: 0,
        node_count: 21,
        relation_count: 24,
        message: 'Neo4j 已就绪',
      },
    }),
    getGraphViewApi: async () => {
      viewCalls += 1
      return {
        data: {
          nodes: [
            { id: 'paper_1', label: 'Paper', name: 'GraphRAG 演示图' },
            { id: 'method_1', label: 'Method', name: 'GraphRAG' },
          ],
          relationships: [
            { id: 'rel_1', source_id: 'paper_1', target_id: 'method_1', type: 'PROPOSES' },
          ],
          label_counts: { Paper: 1, Method: 1 },
          relation_type_counts: { PROPOSES: 1 },
        },
      }
    },
    graphDraftApi: async () => ({ data: {} }),
    graphExecuteApi: async () => ({ data: {} }),
    reconnectGraphApi: async () => ({ data: {} }),
    rebuildGraphDemoApi: async (kind) => {
      rebuildKind = kind
      return {
        data: {
          success: true,
          kind,
          message: '已切换到论文演示图。',
          graph_summary: {
            ready: true,
            configured: true,
            dependency_installed: true,
            neo4j_connected: true,
            database: 'neo4j',
            paper_count: 3,
            node_count: 16,
            relation_count: 16,
            message: 'Neo4j 已就绪',
          },
        },
      }
    },
  })

  const workspace = useGraphWorkspace()
  workspace.graphFilters.value.query = 'stale-query'

  const result = await workspace.rebuildDemo('paper')

  assert.equal(rebuildKind, 'paper')
  assert.equal(result.kind, 'paper')
  assert.equal(workspace.demoBusy.value, false)
  assert.equal(workspace.summary.value.paper_count, 3)
  assert.equal(workspace.summary.value.node_count, 16)
  assert.equal(workspace.graphFilters.value.query, '')
  assert.equal(workspace.graphView.value.nodes.length, 2)
  assert.equal(workspace.graphView.value.relationships.length, 1)
  assert.equal(viewCalls, 1)
  assert.match(workspace.feedback.value.text, /论文演示图/)

  resetGraphWorkspaceDependencies()
})

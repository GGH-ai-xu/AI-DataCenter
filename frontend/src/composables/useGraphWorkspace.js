import { computed, getCurrentInstance, onMounted, ref, watch } from 'vue'

import {
  getGraphSummary as getGraphSummaryRequest,
  getGraphNeighbors as getGraphNeighborsRequest,
  getGraphView as getGraphViewRequest,
  graphDraft as graphDraftRequest,
  graphExecute as graphExecuteRequest,
  graphQa as graphQaRequest,
  rebuildGraphDemo as rebuildGraphDemoRequest,
  reconnectGraph as reconnectGraphRequest,
} from '../services/api.js'


function defaultSummary() {
  return {
    ready: false,
    configured: false,
    dependency_installed: false,
    neo4j_connected: false,
    database: 'neo4j',
    paper_count: 0,
    node_count: 0,
    relation_count: 0,
    local_start_available: false,
    local_start_message: '',
    message: 'Neo4j 尚未连接',
  }
}

function defaultGraphView() {
  return {
    query: '',
    limit: 60,
    nodes: [],
    relationships: [],
    label_counts: {},
    relation_type_counts: {},
    message: '图库视图尚未加载',
  }
}

function defaultGraphQaResult() {
  return {
    question: '',
    summary: '',
    answer: '',
    confidence: 'low',
    evidence: [],
    follow_ups: [],
    used_llm: false,
    matched_node_count: 0,
    matched_relationship_count: 0,
    paper_titles: [],
    evidence_nodes: [],
    evidence_relationships: [],
  }
}

function summarizeGraphViewData(nodes = [], relationships = []) {
  const labelCounts = {}
  const relationTypeCounts = {}
  for (const node of Array.isArray(nodes) ? nodes : []) {
    const label = String(node?.label || 'Unknown')
    labelCounts[label] = (labelCounts[label] || 0) + 1
  }
  for (const relationship of Array.isArray(relationships) ? relationships : []) {
    const type = String(relationship?.type || 'UNKNOWN')
    relationTypeCounts[type] = (relationTypeCounts[type] || 0) + 1
  }
  return {
    labelCounts,
    relationTypeCounts,
  }
}

function normalizeGraphViewPayload(payload = {}, fallback = {}) {
  const nodes = Array.isArray(payload?.nodes) ? payload.nodes : Array.isArray(fallback?.nodes) ? fallback.nodes : []
  const relationships = Array.isArray(payload?.relationships)
    ? payload.relationships
    : Array.isArray(fallback?.relationships) ? fallback.relationships : []
  const counts = summarizeGraphViewData(nodes, relationships)
  const labelCounts = payload?.label_counts && Object.keys(payload.label_counts).length
    ? payload.label_counts
    : counts.labelCounts
  const relationTypeCounts = payload?.relation_type_counts && Object.keys(payload.relation_type_counts).length
    ? payload.relation_type_counts
    : counts.relationTypeCounts

  return {
    ...defaultGraphView(),
    ...fallback,
    ...(payload || {}),
    nodes,
    relationships,
    label_counts: labelCounts,
    relation_type_counts: relationTypeCounts,
  }
}

function mergeGraphViewPayload(currentView = {}, incomingView = {}) {
  const current = normalizeGraphViewPayload(currentView)
  const incoming = normalizeGraphViewPayload(incomingView)
  const nodeMap = new Map()
  const relationshipMap = new Map()

  for (const node of current.nodes) {
    if (!node?.id) continue
    nodeMap.set(node.id, node)
  }
  for (const node of incoming.nodes) {
    if (!node?.id) continue
    nodeMap.set(node.id, {
      ...(nodeMap.get(node.id) || {}),
      ...node,
    })
  }

  for (const relationship of current.relationships) {
    if (!relationship?.id) continue
    relationshipMap.set(relationship.id, relationship)
  }
  for (const relationship of incoming.relationships) {
    if (!relationship?.id) continue
    relationshipMap.set(relationship.id, {
      ...(relationshipMap.get(relationship.id) || {}),
      ...relationship,
    })
  }

  const nodes = [...nodeMap.values()]
  const relationships = [...relationshipMap.values()]
  const counts = summarizeGraphViewData(nodes, relationships)

  return {
    ...current,
    ...incoming,
    query: current.query,
    limit: current.limit,
    message: incoming.message || current.message,
    nodes,
    relationships,
    label_counts: counts.labelCounts,
    relation_type_counts: counts.relationTypeCounts,
  }
}


function defaultDeps() {
  return {
    getGraphSummaryApi: getGraphSummaryRequest,
    getGraphNeighborsApi: getGraphNeighborsRequest,
    getGraphViewApi: getGraphViewRequest,
    graphDraftApi: graphDraftRequest,
    graphExecuteApi: graphExecuteRequest,
    graphQaApi: graphQaRequest,
    rebuildGraphDemoApi: rebuildGraphDemoRequest,
    reconnectGraphApi: reconnectGraphRequest,
    requestTimeoutMs: 20000,
  }
}


let graphWorkspaceDeps = null


function resolveDeps() {
  return graphWorkspaceDeps || defaultDeps()
}


export function setGraphWorkspaceDependencies(overrides = {}) {
  graphWorkspaceDeps = {
    ...defaultDeps(),
    ...overrides,
  }
}


export function resetGraphWorkspaceDependencies() {
  graphWorkspaceDeps = null
}


export function useGraphWorkspace() {
  const form = ref({
    title: '',
    abstract: '',
    content: '',
    mode: 'paper',
    source: 'paper',
    sourceType: 'paper',
    domainTag: '',
    scenario: '',
  })
  const summary = ref(defaultSummary())
  const feedback = ref(null)
  const refreshBusy = ref(false)
  const draftBusy = ref(false)
  const executeBusy = ref(false)
  const reconnectBusy = ref(false)
  const demoBusy = ref(false)
  const viewBusy = ref(false)
  const expandBusy = ref(false)
  const qaBusy = ref(false)
  const expandingNodeId = ref('')
  const draftResult = ref(null)
  const executionResult = ref(null)
  const graphFilters = ref({
    query: '',
    limit: 60,
  })
  const graphView = ref(defaultGraphView())
  const selectedGraphNodeId = ref('')
  const qaForm = ref({
    question: '',
  })
  const qaResult = ref(defaultGraphQaResult())

  const canGenerate = computed(() => {
    const payload = form.value
    return Boolean(payload.title.trim() && (payload.abstract.trim() || payload.content.trim()))
  })
  const canExecute = computed(() =>
    Boolean(draftResult.value?.graph?.nodes?.length)
    && summary.value.neo4j_connected
    && !executeBusy.value
  )
  const canAsk = computed(() =>
    Boolean(String(qaForm.value.question || '').trim())
    && summary.value.neo4j_connected
    && !qaBusy.value
  )
  const selectedGraphNode = computed(() =>
    graphView.value.nodes.find((item) => item.id === selectedGraphNodeId.value) || null
  )

  watch(() => form.value.mode, (nextMode, previousMode) => {
    const normalizedMode = nextMode === 'optimization' ? 'optimization' : 'paper'
    if (form.value.mode !== normalizedMode) {
      form.value.mode = normalizedMode
      return
    }
    form.value.source = normalizedMode
    const previousDefaultSourceType = previousMode === 'optimization' ? 'rule' : 'paper'
    const nextDefaultSourceType = normalizedMode === 'optimization' ? 'rule' : 'paper'
    const currentSourceType = String(form.value.sourceType || '').trim()
    if (!currentSourceType || currentSourceType === previousDefaultSourceType) {
      form.value.sourceType = nextDefaultSourceType
    }
  }, { immediate: true })

  function requestTimeoutMs() {
    return Number(resolveDeps().requestTimeoutMs || 20000)
  }

  async function runWithTimeout(task, timeoutMessage) {
    let timerId = null
    try {
      return await Promise.race([
        task(),
        new Promise((_, reject) => {
          timerId = globalThis.setTimeout(() => {
            reject(new Error(timeoutMessage))
          }, requestTimeoutMs())
        }),
      ])
    } finally {
      if (timerId !== null) {
        globalThis.clearTimeout(timerId)
      }
    }
  }

  function resetWorkspaceState(message = '已重置图谱操作状态，请重新尝试。') {
    draftBusy.value = false
    executeBusy.value = false
    reconnectBusy.value = false
    demoBusy.value = false
    viewBusy.value = false
    expandBusy.value = false
    qaBusy.value = false
    expandingNodeId.value = ''
    feedback.value = {
      type: 'error',
      text: message,
    }
  }

  async function refreshSummary(options = {}) {
    const silent = Boolean(options.silent)
    if (refreshBusy.value || draftBusy.value || executeBusy.value) {
      return summary.value
    }
    refreshBusy.value = true
    try {
      const response = await runWithTimeout(
        () => resolveDeps().getGraphSummaryApi(),
        '图库状态刷新超时，请重试',
      )
      summary.value = {
        ...defaultSummary(),
        ...(response?.data || {}),
      }
      if (!silent) {
        feedback.value = {
          type: 'success',
          text: `图库状态已刷新：${summary.value.node_count || 0} 个节点，${summary.value.relation_count || 0} 条关系。`,
        }
      }
      return summary.value
    } catch (error) {
      summary.value = {
        ...defaultSummary(),
        message: error?.response?.data?.detail || error?.message || '读取图谱状态失败',
      }
      if (!silent) {
        feedback.value = {
          type: 'error',
          text: summary.value.message,
        }
      }
      return summary.value
    } finally {
      refreshBusy.value = false
    }
  }

  function selectGraphNode(nodeId = '') {
    selectedGraphNodeId.value = String(nodeId || '')
  }

  async function refreshGraphView(options = {}) {
    const silent = Boolean(options.silent)
    if (viewBusy.value || reconnectBusy.value || expandBusy.value) {
      return graphView.value
    }
    viewBusy.value = true
    try {
      const response = await runWithTimeout(
        () => resolveDeps().getGraphViewApi({
          query: String(graphFilters.value.query || '').trim(),
          limit: Number(graphFilters.value.limit || 60),
        }),
        '图库视图刷新超时，请重试',
      )
      graphView.value = normalizeGraphViewPayload(response?.data, {
        query: String(graphFilters.value.query || '').trim(),
        limit: Number(graphFilters.value.limit || 60),
      })
      expandingNodeId.value = ''
      if (!graphView.value.nodes.some((item) => item.id === selectedGraphNodeId.value)) {
        selectedGraphNodeId.value = graphView.value.nodes[0]?.id || ''
      }
      if (!silent) {
        feedback.value = {
          type: 'success',
          text: `图库视图已刷新：当前展示 ${graphView.value.nodes.length || 0} 个节点，${graphView.value.relationships.length || 0} 条关系。`,
        }
      }
      return graphView.value
    } catch (error) {
      graphView.value = normalizeGraphViewPayload({
        query: String(graphFilters.value.query || '').trim(),
        limit: Number(graphFilters.value.limit || 60),
        message: error?.response?.data?.detail || error?.message || '读取图库视图失败',
      })
      expandingNodeId.value = ''
      selectedGraphNodeId.value = ''
      if (!silent) {
        feedback.value = {
          type: 'error',
          text: graphView.value.message,
        }
      }
      return graphView.value
    } finally {
      viewBusy.value = false
    }
  }

  async function expandGraphNode(nodeId = '', options = {}) {
    const silent = Boolean(options.silent)
    const normalizedNodeId = String(nodeId || selectedGraphNodeId.value || '').trim()
    const expandLimit = Number(options.limit || 24)
    if (!normalizedNodeId || viewBusy.value || reconnectBusy.value || expandBusy.value) {
      return graphView.value
    }

    expandBusy.value = true
    expandingNodeId.value = normalizedNodeId
    selectedGraphNodeId.value = normalizedNodeId
    try {
      const response = await runWithTimeout(
        () => resolveDeps().getGraphNeighborsApi({
          node_id: normalizedNodeId,
          limit: expandLimit,
        }),
        '图谱邻居展开超时，请重试',
      )
      graphView.value = mergeGraphViewPayload(graphView.value, response?.data || {})
      if (!graphView.value.nodes.some((item) => item.id === selectedGraphNodeId.value)) {
        selectedGraphNodeId.value = graphView.value.nodes[0]?.id || ''
      }
      if (!silent) {
        const fetchedCount = Number(response?.data?.fetched_neighbor_count || 0)
        feedback.value = {
          type: 'success',
          text: fetchedCount > 0 ? `已展开 ${fetchedCount} 个邻居节点。` : '当前节点没有更多邻居可展开。',
        }
      }
      return graphView.value
    } catch (error) {
      if (!silent) {
        feedback.value = {
          type: 'error',
          text: error?.response?.data?.detail || error?.message || '图谱邻居展开失败',
        }
      }
      return graphView.value
    } finally {
      expandBusy.value = false
      expandingNodeId.value = ''
    }
  }

  async function generateDraft() {
    if (draftBusy.value || executeBusy.value || reconnectBusy.value || expandBusy.value || !canGenerate.value) return null
    draftBusy.value = true
    feedback.value = null
    executionResult.value = null
    try {
      const response = await runWithTimeout(
        () => resolveDeps().graphDraftApi({
          title: form.value.title.trim(),
          abstract: form.value.abstract.trim(),
          content: form.value.content.trim(),
          mode: form.value.mode,
          source: form.value.mode,
          source_type: form.value.sourceType,
          domain_tag: form.value.domainTag.trim(),
          scenario: form.value.scenario.trim(),
        }),
        '图谱草稿生成超时，请重试',
      )
      draftResult.value = response?.data || null
      feedback.value = {
        type: 'success',
        text: `已生成图谱草稿：${draftResult.value?.summary?.node_count || 0} 个节点，${draftResult.value?.summary?.relation_count || 0} 条关系。`,
      }
      return draftResult.value
    } catch (error) {
      draftResult.value = null
      feedback.value = {
        type: 'error',
        text: error?.response?.data?.detail || error?.message || '图谱草稿生成失败',
      }
      return null
    } finally {
      draftBusy.value = false
    }
  }

  async function executeImport() {
    if (draftBusy.value || executeBusy.value || reconnectBusy.value || expandBusy.value || !draftResult.value?.graph) return null
    executeBusy.value = true
    feedback.value = null
    try {
      const draftGraph = draftResult.value.graph || {}
      const response = await runWithTimeout(
        () => resolveDeps().graphExecuteApi({
          graph: {
            ...draftGraph,
            mode: draftGraph.mode || form.value.mode,
            source: draftGraph.source || form.value.mode,
            source_type: draftGraph.source_type || form.value.sourceType,
            domain_tag: draftGraph.domain_tag || form.value.domainTag.trim(),
            scenario: draftGraph.scenario || form.value.scenario.trim(),
          },
          cypher: draftResult.value.cypher || '',
          source: draftGraph.source || form.value.mode,
        }),
        '图谱写入超时，请重试',
      )
      executionResult.value = response?.data || null
      if (executionResult.value?.graph_summary) {
        summary.value = {
          ...defaultSummary(),
          ...executionResult.value.graph_summary,
        }
      } else {
        await refreshSummary()
      }
      await refreshGraphView({ silent: true })
      feedback.value = {
        type: 'success',
        text: executionResult.value?.message || '图谱写入成功',
      }
      return executionResult.value
    } catch (error) {
      executionResult.value = null
      feedback.value = {
        type: 'error',
        text: error?.response?.data?.detail || error?.message || '图谱写入失败',
      }
      await refreshSummary()
      return null
    } finally {
      executeBusy.value = false
    }
  }

  async function recoverConnection() {
    if (refreshBusy.value || draftBusy.value || executeBusy.value || reconnectBusy.value || expandBusy.value) return null
    reconnectBusy.value = true
    feedback.value = null
    try {
      const response = await runWithTimeout(
        () => resolveDeps().reconnectGraphApi(),
        '本地 Neo4j 拉起超时，请重试',
      )
      const payload = response?.data || null
      if (payload?.graph_summary) {
        summary.value = {
          ...defaultSummary(),
          ...payload.graph_summary,
        }
      } else {
        await refreshSummary({ silent: true })
      }
      await refreshGraphView({ silent: true })
      feedback.value = {
        type: 'success',
        text: payload?.message || 'Neo4j 已完成重连。',
      }
      return payload
    } catch (error) {
      feedback.value = {
        type: 'error',
        text: error?.response?.data?.detail || error?.message || 'Neo4j 重连失败',
      }
      await refreshSummary({ silent: true })
      return null
    } finally {
      reconnectBusy.value = false
    }
  }

  async function rebuildDemo(kind = 'optimization') {
    const normalizedKind = String(kind || 'optimization').trim() === 'paper' ? 'paper' : 'optimization'
    if (refreshBusy.value || draftBusy.value || executeBusy.value || reconnectBusy.value || expandBusy.value || demoBusy.value) return null
    demoBusy.value = true
    feedback.value = null
    try {
      const response = await runWithTimeout(
        () => resolveDeps().rebuildGraphDemoApi(normalizedKind),
        '演示图库切换超时，请重试',
      )
      const payload = response?.data || null
      if (payload?.graph_summary) {
        summary.value = {
          ...defaultSummary(),
          ...payload.graph_summary,
        }
      } else {
        await refreshSummary({ silent: true })
      }
      graphFilters.value.query = ''
      await refreshGraphView({ silent: true })
      feedback.value = {
        type: 'success',
        text: payload?.message || '演示图库已切换。',
      }
      return payload
    } catch (error) {
      feedback.value = {
        type: 'error',
        text: error?.response?.data?.detail || error?.message || '演示图库切换失败',
      }
      await refreshSummary({ silent: true })
      return null
    } finally {
      demoBusy.value = false
    }
  }

  async function askGraphQuestion(nextQuestion = '') {
    const question = String(nextQuestion || qaForm.value.question || '').trim()
    if (!question || qaBusy.value || reconnectBusy.value || draftBusy.value || executeBusy.value) {
      return null
    }

    qaBusy.value = true
    qaForm.value.question = question
    feedback.value = null
    try {
      const response = await runWithTimeout(
        () => resolveDeps().graphQaApi({ question }),
        '图谱问答超时，请重试',
      )
      qaResult.value = {
        ...defaultGraphQaResult(),
        ...(response?.data || {}),
      }
      const firstNodeId = qaResult.value.evidence_nodes?.[0]?.id || ''
      if (firstNodeId) {
        selectedGraphNodeId.value = firstNodeId
      }
      feedback.value = {
        type: 'success',
        text: qaResult.value.summary || '图谱问答已生成。',
      }
      return qaResult.value
    } catch (error) {
      qaResult.value = {
        ...defaultGraphQaResult(),
        question,
        summary: error?.response?.data?.detail || error?.message || '图谱问答失败',
      }
      feedback.value = {
        type: 'error',
        text: qaResult.value.summary,
      }
      return null
    } finally {
      qaBusy.value = false
    }
  }

  if (getCurrentInstance()) {
    onMounted(() => {
      void refreshSummary()
    })
  }

  return {
    form,
    summary,
    feedback,
    graphFilters,
    graphView,
    selectedGraphNodeId,
    selectedGraphNode,
    refreshBusy,
    draftBusy,
    executeBusy,
    reconnectBusy,
    demoBusy,
    viewBusy,
    expandBusy,
    qaBusy,
    expandingNodeId,
    draftResult,
    executionResult,
    qaForm,
    qaResult,
    canGenerate,
    canExecute,
    canAsk,
    refreshSummary,
    refreshGraphView,
    expandGraphNode,
    generateDraft,
    executeImport,
    recoverConnection,
    rebuildDemo,
    askGraphQuestion,
    selectGraphNode,
    resetWorkspaceState,
  }
}

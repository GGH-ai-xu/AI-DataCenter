export const LABEL_PRIORITY = {
  Paper: 0,
  Policy: 1,
  OptimizationStrategy: 2,
  Constraint: 3,
  PowerBudget: 4,
  CarbonTarget: 5,
  TaskType: 6,
  TimePeriod: 7,
  Metric: 8,
  CodeTemplate: 9,
  API: 10,
  Cluster: 11,
  GPU: 12,
  Task: 13,
  Method: 14,
  Dataset: 15,
  Action: 16,
}

export const LABEL_META = {
  Paper: { color: '#7F8EFF', size: 62 },
  Policy: { color: '#9CA8FF', size: 58 },
  OptimizationStrategy: { color: '#71B7FF', size: 56 },
  Constraint: { color: '#FFB264', size: 50 },
  PowerBudget: { color: '#67D7B5', size: 48 },
  CarbonTarget: { color: '#63D3D8', size: 46 },
  TaskType: { color: '#F4B95D', size: 44 },
  TimePeriod: { color: '#C98FFF', size: 42 },
  Metric: { color: '#FF6F96', size: 40 },
  CodeTemplate: { color: '#7BE0FF', size: 38 },
  API: { color: '#B5C0FF', size: 36 },
  Cluster: { color: '#68D1AE', size: 34 },
  GPU: { color: '#84C5FF', size: 32 },
  Task: { color: '#F4B95D', size: 42 },
  Method: { color: '#6EB8FF', size: 50 },
  Dataset: { color: '#68D1AE', size: 40 },
  Action: { color: '#FFD76F', size: 34 },
  Unknown: { color: '#9EA8C0', size: 34 },
}

export const RELATION_COLOR = {
  PROPOSES: '#97A5FF',
  SOLVES: '#F4B95D',
  USES: '#6EB8FF',
  ACHIEVES: '#FF6F96',
  EVALUATES: '#68D1AE',
  CONSTRAINS: '#FFB264',
  APPLIES_TO: '#C98FFF',
  OPTIMIZES: '#67D7B5',
  LIMITS: '#63D3D8',
  USES_TEMPLATE: '#7BE0FF',
  CALLS_API: '#B5C0FF',
  AFFECTS: '#FF8BA7',
  TRIGGERS: '#9CA8FF',
  REQUIRES: '#FFD76F',
  BELONGS_TO: '#8ED8BF',
  RUNS_ON: '#7DAEFF',
}

function normalizeText(value) {
  return String(value || '').trim()
}

function normalizeLowerText(value) {
  return normalizeText(value).toLowerCase()
}

function escapeHtml(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

function summarizeText(value, limit = 140) {
  const text = normalizeText(value)
  if (!text) return ''
  return text.length > limit ? `${text.slice(0, limit).trim()}...` : text
}

function nodeMeta(label) {
  return LABEL_META[label] || LABEL_META.Unknown
}

function compareByPriority(left = '', right = '') {
  const diff = (LABEL_PRIORITY[left] ?? 99) - (LABEL_PRIORITY[right] ?? 99)
  if (diff !== 0) return diff
  return String(left).localeCompare(String(right), 'zh-CN')
}

function buildNodeHaystack(node = {}) {
  return [
    node.name,
    node.label,
    node.paper_title,
    node.description,
    node.source,
    ...(Array.isArray(node.labels) ? node.labels : []),
  ].map((value) => normalizeLowerText(value)).join(' ')
}

function formatCsvCell(value) {
  const text = String(value ?? '')
  if (text.includes(',') || text.includes('"') || text.includes('\n')) {
    return `"${text.replaceAll('"', '""')}"`
  }
  return text
}

function formatPercent(value, digits = 1) {
  return `${(Number(value || 0) * 100).toFixed(digits)}%`
}

export function sortGraphLabels(labels = []) {
  return [...labels].sort(compareByPriority)
}

export function countGraphValues(items = [], field, fallback = 'Unknown') {
  const counts = {}
  for (const item of Array.isArray(items) ? items : []) {
    const key = String(item?.[field] || fallback)
    counts[key] = (counts[key] || 0) + 1
  }
  return counts
}

export function buildGraphDegreeState(graphView = {}) {
  const nodes = Array.isArray(graphView.nodes) ? graphView.nodes : []
  const relationships = Array.isArray(graphView.relationships) ? graphView.relationships : []
  const degreeMap = new Map(nodes.map((node) => [node.id, 0]))
  const inDegreeMap = new Map(nodes.map((node) => [node.id, 0]))
  const outDegreeMap = new Map(nodes.map((node) => [node.id, 0]))

  for (const relationship of relationships) {
    const sourceId = relationship?.source_id
    const targetId = relationship?.target_id
    if (!sourceId || !targetId) continue
    degreeMap.set(sourceId, (degreeMap.get(sourceId) || 0) + 1)
    degreeMap.set(targetId, (degreeMap.get(targetId) || 0) + 1)
    outDegreeMap.set(sourceId, (outDegreeMap.get(sourceId) || 0) + 1)
    inDegreeMap.set(targetId, (inDegreeMap.get(targetId) || 0) + 1)
  }

  return {
    degreeMap,
    inDegreeMap,
    outDegreeMap,
  }
}

export function buildFilteredGraph(graphView = {}, filters = {}) {
  const allNodes = Array.isArray(graphView.nodes) ? graphView.nodes : []
  const allRelationships = Array.isArray(graphView.relationships) ? graphView.relationships : []
  const labelSet = new Set(Array.isArray(filters.labels) ? filters.labels : allNodes.map((node) => node.label))
  const relationTypeSet = new Set(Array.isArray(filters.relationTypes) ? filters.relationTypes : [])
  const sourceFilter = normalizeLowerText(filters.source)
  const paperQuery = normalizeLowerText(filters.paperQuery)

  let nodes = allNodes.filter((node) => labelSet.has(node.label))
  if (sourceFilter && sourceFilter !== 'all') {
    nodes = nodes.filter((node) => normalizeLowerText(node.source) === sourceFilter)
  }
  if (paperQuery) {
    nodes = nodes.filter((node) => buildNodeHaystack(node).includes(paperQuery))
  }

  let nodeIdSet = new Set(nodes.map((node) => node.id))
  let relationships = allRelationships.filter((relationship) =>
    nodeIdSet.has(relationship.source_id) && nodeIdSet.has(relationship.target_id)
  )
  if (relationTypeSet.size) {
    relationships = relationships.filter((relationship) => relationTypeSet.has(relationship.type))
  }

  let focusedNodeIds = []
  const focusNodeId = normalizeText(filters.focusNodeId)
  if (filters.focusMode && focusNodeId && nodeIdSet.has(focusNodeId)) {
    const focusSet = new Set([focusNodeId])
    for (const relationship of relationships) {
      if (relationship.source_id === focusNodeId) focusSet.add(relationship.target_id)
      if (relationship.target_id === focusNodeId) focusSet.add(relationship.source_id)
    }
    focusedNodeIds = [...focusSet]
    nodes = nodes.filter((node) => focusSet.has(node.id))
    nodeIdSet = new Set(nodes.map((node) => node.id))
    relationships = relationships.filter((relationship) =>
      nodeIdSet.has(relationship.source_id) && nodeIdSet.has(relationship.target_id)
    )
  }

  return {
    ...graphView,
    nodes,
    relationships,
    label_counts: countGraphValues(nodes, 'label', 'Unknown'),
    relation_type_counts: countGraphValues(relationships, 'type', 'UNKNOWN'),
    focused_node_ids: focusedNodeIds,
  }
}

export function buildGraphInsights(graphView = {}) {
  const nodes = Array.isArray(graphView.nodes) ? graphView.nodes : []
  const relationships = Array.isArray(graphView.relationships) ? graphView.relationships : []
  const { degreeMap } = buildGraphDegreeState(graphView)
  const adjacency = new Map(nodes.map((node) => [node.id, new Set()]))
  const nodeCount = nodes.length
  const relationshipCount = relationships.length
  const labelCounts = countGraphValues(nodes, 'label', 'Unknown')
  const relationTypeCounts = countGraphValues(relationships, 'type', 'UNKNOWN')
  const paperTitles = new Set()
  const topicTitles = new Set()
  const sources = new Set()

  for (const node of nodes) {
    if (normalizeText(node.paper_title)) {
      topicTitles.add(node.paper_title)
    }
    if (node.label === 'Paper' && normalizeText(node.paper_title)) {
      paperTitles.add(node.paper_title)
    }
    if (normalizeText(node.source)) {
      sources.add(node.source)
    }
  }

  for (const relationship of relationships) {
    const sourceId = relationship?.source_id
    const targetId = relationship?.target_id
    if (!sourceId || !targetId) continue
    adjacency.get(sourceId)?.add(targetId)
    adjacency.get(targetId)?.add(sourceId)
  }

  let isolatedNodeCount = 0
  let totalDegree = 0
  for (const node of nodes) {
    const degree = degreeMap.get(node.id) || 0
    totalDegree += degree
    if (degree === 0) isolatedNodeCount += 1
  }

  let componentCount = 0
  let largestComponentSize = 0
  const visited = new Set()
  for (const node of nodes) {
    if (visited.has(node.id)) continue
    componentCount += 1
    let size = 0
    const stack = [node.id]
    visited.add(node.id)
    while (stack.length) {
      const currentId = stack.pop()
      size += 1
      for (const neighborId of adjacency.get(currentId) || []) {
        if (visited.has(neighborId)) continue
        visited.add(neighborId)
        stack.push(neighborId)
      }
    }
    largestComponentSize = Math.max(largestComponentSize, size)
  }

  const averageDegree = nodeCount ? totalDegree / nodeCount : 0
  const density = nodeCount > 1 ? relationshipCount / (nodeCount * (nodeCount - 1)) : 0

  return {
    nodeCount,
    relationshipCount,
    labelCounts,
    relationTypeCounts,
    paperCount: paperTitles.size,
    topicCount: topicTitles.size,
    sourceCount: sources.size,
    componentCount,
    isolatedNodeCount,
    largestComponentSize,
    averageDegree,
    averageDegreeText: averageDegree.toFixed(1),
    density,
    densityText: formatPercent(density, 1),
  }
}

export function buildGraphTableRows(graphView = {}, options = {}) {
  const rowsSource = Array.isArray(graphView.nodes) ? graphView.nodes : []
  const { degreeMap, inDegreeMap, outDegreeMap } = buildGraphDegreeState(graphView)
  const sortBy = normalizeText(options.sortBy) || 'degree'
  const sortDirection = options.sortDirection === 'asc' ? 'asc' : 'desc'
  const factor = sortDirection === 'asc' ? 1 : -1

  const rows = rowsSource.map((node) => ({
    ...node,
    degree: degreeMap.get(node.id) || 0,
    in_degree: inDegreeMap.get(node.id) || 0,
    out_degree: outDegreeMap.get(node.id) || 0,
    description_preview: summarizeText(node.description, 110),
  }))

  rows.sort((left, right) => {
    let compareValue = 0
    if (sortBy === 'name') {
      compareValue = normalizeText(left.name).localeCompare(normalizeText(right.name), 'zh-CN')
    } else if (sortBy === 'label') {
      compareValue = compareByPriority(left.label, right.label)
    } else if (sortBy === 'paper_title') {
      compareValue = normalizeText(left.paper_title).localeCompare(normalizeText(right.paper_title), 'zh-CN')
    } else if (sortBy === 'source') {
      compareValue = normalizeText(left.source).localeCompare(normalizeText(right.source), 'zh-CN')
    } else if (sortBy === 'in_degree') {
      compareValue = (left.in_degree || 0) - (right.in_degree || 0)
    } else if (sortBy === 'out_degree') {
      compareValue = (left.out_degree || 0) - (right.out_degree || 0)
    } else {
      compareValue = (left.degree || 0) - (right.degree || 0)
    }
    if (compareValue !== 0) return compareValue * factor
    return normalizeText(left.name).localeCompare(normalizeText(right.name), 'zh-CN')
  })

  return rows
}

export function buildGraphHotspotRanking(graphView = {}, options = {}) {
  const limit = Math.max(1, Math.min(Number(options.limit || 8), 20))
  return buildGraphTableRows(graphView, {
    sortBy: 'degree',
    sortDirection: 'desc',
  }).slice(0, limit).map((row, index) => ({
    ...row,
    rank: index + 1,
  }))
}

export function buildGraphPaperGroups(graphView = {}, options = {}) {
  const limit = Math.max(1, Math.min(Number(options.limit || 6), 24))
  const nodes = Array.isArray(graphView.nodes) ? graphView.nodes : []
  const relationships = Array.isArray(graphView.relationships) ? graphView.relationships : []
  const nodeMap = new Map(nodes.map((node) => [node.id, node]))
  const paperMap = new Map()

  function ensurePaperGroup(title) {
    if (!paperMap.has(title)) {
      paperMap.set(title, {
        title,
        node_count: 0,
        relation_count: 0,
        labels: {},
        sources: new Set(),
      })
    }
    return paperMap.get(title)
  }

  for (const node of nodes) {
    const title = normalizeText(node.paper_title) || '未标注主题'
    const group = ensurePaperGroup(title)
    group.node_count += 1
    group.labels[node.label || 'Unknown'] = (group.labels[node.label || 'Unknown'] || 0) + 1
    if (normalizeText(node.source)) {
      group.sources.add(node.source)
    }
  }

  for (const relationship of relationships) {
    const explicitTitle = normalizeText(relationship.paper_title)
    const sourceTitle = normalizeText(nodeMap.get(relationship.source_id)?.paper_title)
    const targetTitle = normalizeText(nodeMap.get(relationship.target_id)?.paper_title)
    const title = explicitTitle || sourceTitle || targetTitle || '未标注主题'
    ensurePaperGroup(title).relation_count += 1
  }

  return [...paperMap.values()]
    .map((group) => ({
      ...group,
      source_count: group.sources.size,
      sources: [...group.sources],
    }))
    .sort((left, right) => {
      if (right.node_count !== left.node_count) return right.node_count - left.node_count
      if (right.relation_count !== left.relation_count) return right.relation_count - left.relation_count
      return normalizeText(left.title).localeCompare(normalizeText(right.title), 'zh-CN')
    })
    .slice(0, limit)
}

export function buildGraphJsonExport(graphView = {}) {
  return JSON.stringify({
    exported_at: new Date().toISOString(),
    node_count: Array.isArray(graphView.nodes) ? graphView.nodes.length : 0,
    relationship_count: Array.isArray(graphView.relationships) ? graphView.relationships.length : 0,
    nodes: Array.isArray(graphView.nodes) ? graphView.nodes : [],
    relationships: Array.isArray(graphView.relationships) ? graphView.relationships : [],
  }, null, 2)
}

export function buildGraphCsvExport(rows = []) {
  const headers = ['节点', '标签', '所属主题', '来源', '总连接数', '入边', '出边', '描述']
  const body = rows.map((row) => ([
    formatCsvCell(row.name),
    formatCsvCell(row.label),
    formatCsvCell(row.paper_title),
    formatCsvCell(row.source),
    formatCsvCell(row.degree),
    formatCsvCell(row.in_degree),
    formatCsvCell(row.out_degree),
    formatCsvCell(row.description),
  ]).join(','))
  return [headers.join(','), ...body].join('\n')
}

export function buildGraphDefenseOverview(graphView = {}) {
  const insights = buildGraphInsights(graphView)
  const hotspots = buildGraphHotspotRanking(graphView, { limit: 6 })
  const paperGroups = buildGraphPaperGroups(graphView, { limit: 6 })
  const dominantRelationEntry = Object.entries(insights.relationTypeCounts || {})
    .sort((left, right) => {
      if (right[1] !== left[1]) return right[1] - left[1]
      return String(left[0]).localeCompare(String(right[0]), 'en')
    })[0] || null
  const leadMethod = hotspots.find((item) => item.label === 'Method') || hotspots[0] || null
  const topPaper = paperGroups[0] || null
  const taskCount = insights.labelCounts.Task || 0
  const datasetCount = insights.labelCounts.Dataset || 0
  const metricCount = insights.labelCounts.Metric || 0
  const entryScopeLabel = insights.paperCount
    ? `${insights.paperCount} 篇`
    : `${insights.topicCount || paperGroups.length} 个主题`

  const focusCards = [
    {
      label: '图谱规模',
      value: `${entryScopeLabel} / ${insights.nodeCount} 节点 / ${insights.relationshipCount} 关系`,
      detail: '适合在开场讲解时先说明图谱覆盖范围。',
    },
    {
      label: '核心实体',
      value: leadMethod ? leadMethod.name : '待补充',
      detail: leadMethod
        ? `当前连接度最高，累计 ${leadMethod.degree} 条边。`
        : (insights.paperCount ? '导入更多论文后会自动突出热点实体。' : '补充更多策略、约束和模板后会自动突出热点实体。'),
    },
    {
      label: '主导关系',
      value: dominantRelationEntry ? dominantRelationEntry[0] : '暂无',
      detail: dominantRelationEntry
        ? `当前视图中出现 ${dominantRelationEntry[1]} 次，是最适合解释研究脉络的关系类型。`
        : '当前图谱里还没有足够关系可供展示。',
    },
    {
      label: '覆盖面',
      value: `${taskCount} 任务 / ${datasetCount} 数据集 / ${metricCount} 指标`,
      detail: '可以直接回答“方法落在哪些任务、数据集和指标上”。',
    },
  ]

  const talkingPoints = [
    insights.paperCount
      ? `当前图库已经把 ${insights.paperCount} 篇论文连进一张图里，不再是单篇论文孤立展示。`
      : `当前图库已经形成 ${insights.topicCount || paperGroups.length} 个优化主题，可直接展示策略、约束、预算和模板之间的关系。`,
    leadMethod
      ? `从连接度看，“${leadMethod.name}”是当前最核心的方法节点，说明它处在研究脉络的主干位置。`
      : '当前还没有明显的核心方法节点，适合改从策略、约束和模板关系切入。',
    topPaper
      ? `从单个主题看，“${topPaper.title}”目前最完整，已经展开 ${topPaper.node_count} 个节点和 ${topPaper.relation_count} 条关系。`
      : '当前还没有形成可对比的主题覆盖面。',
    dominantRelationEntry
      ? `从关系类型看，“${dominantRelationEntry[0]}”最突出，适合讲清楚“约束了什么、优化了什么、调用了什么”。`
      : '当前关系类型还不够丰富，建议继续补图。',
    insights.componentCount > 1
      ? `图谱当前分成 ${insights.componentCount} 个连通分量，后续还可以继续补跨主题关联。`
      : '当前主图已经连成一个整体，适合说明不同知识条目之间不是分散的，而是有承接关系的。',
  ].filter(Boolean)

  const judgeQuestions = [
    insights.paperCount ? '这几篇论文之间的共同主线是什么？' : '这些优化策略和约束之间的共同主线是什么？',
    leadMethod ? `为什么说“${leadMethod.name}”是当前图里的核心方法？` : '当前图里最核心的方法节点是谁？',
    topPaper ? `“${topPaper.title}”在图里具体覆盖了哪些节点、关系和约束？` : '目前哪个主题在图里展开得最完整？',
    taskCount ? '当前图谱已经覆盖了哪些任务方向？' : '目前图里还缺哪些任务或数据集？',
  ].filter(Boolean)

  const presentationFlow = [
    insights.paperCount
      ? `先用“${insights.paperCount} 篇论文、${insights.nodeCount} 个节点、${insights.relationshipCount} 条关系”交代图谱规模。`
      : `先用“${entryScopeLabel}、${insights.nodeCount} 个节点、${insights.relationshipCount} 条关系”交代优化图谱规模。`,
    leadMethod
      ? `接着指出热点实体“${leadMethod.name}”，解释它为什么处在研究主线。`
      : '接着从策略、约束和预算关系切入，说明图谱已经具备主线结构。',
    topPaper
      ? `然后展开“${topPaper.title}”，展示单个主题如何连到策略、约束、预算和模板。`
      : '然后切到图谱沙盘，展示节点与关系如何互相连通。',
    '最后切到“图谱问答”，用证据化回答承接进一步提问。',
  ]

  const answerReadyNotes = [
    leadMethod
      ? `热点实体：${leadMethod.name}`
      : (insights.paperCount ? '热点实体：待补更多论文后会更明显' : '热点实体：待补更多优化条目后会更明显'),
    dominantRelationEntry
      ? `主导关系：${dominantRelationEntry[0]}`
      : '主导关系：当前样本仍较少',
    topPaper
      ? `优先展开主题：${topPaper.title}`
      : '优先展开主题：当前无明显优先项',
  ]

  const headline = insights.paperCount
    ? `当前图库已把 ${insights.paperCount} 篇论文收敛进同一张研究关系图。`
    : `当前图库已形成 ${entryScopeLabel} 的优化知识关系图。`
  const subline = insights.paperCount
    ? `图内共有 ${insights.nodeCount} 个节点、${insights.relationshipCount} 条关系，既能看研究主线，也能追到具体方法、任务和数据集。`
    : `图内共有 ${insights.nodeCount} 个节点、${insights.relationshipCount} 条关系，可直接说明约束、预算、策略和代码模板的连接方式。`

  return {
    headline,
    subline,
    focusCards,
    talkingPoints,
    judgeQuestions,
    presentationFlow,
    answerReadyNotes,
  }
}

export function buildGraphViewerOption(graphView = {}, selectedNodeId = '', options = {}) {
  const nodes = Array.isArray(graphView.nodes) ? graphView.nodes : []
  const relationships = Array.isArray(graphView.relationships) ? graphView.relationships : []
  const degreeState = options.degreeState || buildGraphDegreeState(graphView)
  const degreeMap = degreeState.degreeMap || new Map()
  const nodeNameMap = new Map(nodes.map((node) => [node.id, node.name || node.id]))
  const focusedNodeSet = new Set(options.focusedNodeIds || graphView.focused_node_ids || [])
  const focusActive = focusedNodeSet.size > 0
  const categories = Object.keys(LABEL_META).map((label) => ({
    name: label,
    itemStyle: { color: nodeMeta(label).color },
  }))
  const categoryIndex = new Map(categories.map((item, index) => [item.name, index]))

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(18, 26, 46, 0.96)',
      borderColor: 'rgba(127, 142, 255, 0.24)',
      textStyle: { color: '#EDEEF7' },
      formatter: (params) => {
        const data = params.data || {}
        if (params.dataType === 'edge') {
          return [
            `<div><strong>${escapeHtml(data.type || '关系')}</strong></div>`,
            `<div>${escapeHtml(data.source_label || '')} -> ${escapeHtml(data.target_label || '')}</div>`,
            data.description ? `<div style="margin-top: 4px; color: #C6CEE1">${escapeHtml(summarizeText(data.description, 120))}</div>` : '',
          ].join('')
        }
        return [
          `<div><strong>${escapeHtml(data.name || '')}</strong></div>`,
          `<div style="margin-top: 2px; color: #9EA8C0">${escapeHtml(data.label || 'Unknown')}</div>`,
          data.paper_title ? `<div style="margin-top: 4px">主题：${escapeHtml(data.paper_title)}</div>` : '',
          `<div style="margin-top: 4px">连接数：${escapeHtml(degreeMap.get(data.id) || 0)}</div>`,
          data.description ? `<div style="margin-top: 4px; color: #C6CEE1">${escapeHtml(summarizeText(data.description, 120))}</div>` : '',
        ].join('')
      },
    },
    legend: {
      top: 0,
      icon: 'circle',
      textStyle: { color: '#C6CEE1', fontSize: 11 },
      itemWidth: 10,
      itemHeight: 10,
      data: categories.map((item) => item.name),
    },
    animationDuration: 520,
    animationEasingUpdate: 'cubicOut',
    series: [
      {
        type: 'graph',
        layout: 'force',
        roam: true,
        draggable: true,
        emphasis: {
          focus: 'adjacency',
          lineStyle: {
            width: 3,
          },
          label: {
            show: true,
          },
        },
        force: {
          repulsion: 460,
          gravity: 0.05,
          friction: 0.14,
          edgeLength: [86, 176],
        },
        label: {
          show: true,
          position: 'right',
          distance: 6,
          color: '#EDEEF7',
          fontSize: 11,
          formatter: ({ data }) => data.short_name || data.name || '',
        },
        edgeLabel: {
          show: relationships.length <= 18,
          color: '#AAB5D1',
          fontSize: 10,
          formatter: ({ data }) => data.type || '',
        },
        lineStyle: {
          opacity: 0.78,
          curveness: 0.16,
          width: 1.8,
        },
        edgeSymbol: ['none', 'arrow'],
        edgeSymbolSize: [4, 8],
        categories,
        data: nodes.map((node) => {
          const meta = nodeMeta(node.label)
          const selected = node.id === selectedNodeId
          const focused = focusedNodeSet.has(node.id)
          const shortName = node.name && node.name.length > 22
            ? `${node.name.slice(0, 22)}...`
            : (node.name || node.id)
          const degreeBoost = Math.min((degreeMap.get(node.id) || 0) * 3, 18)
          const dimmed = focusActive && !focused
          return {
            ...node,
            category: categoryIndex.get(node.label) ?? categoryIndex.get('Unknown') ?? 0,
            short_name: shortName,
            symbolSize: (selected ? meta.size + 10 : meta.size) + degreeBoost,
            itemStyle: {
              color: meta.color,
              opacity: dimmed ? 0.34 : 0.96,
              borderColor: selected ? '#FFFFFF' : focused ? 'rgba(255,255,255,0.92)' : 'rgba(255,255,255,0.18)',
              borderWidth: selected ? 2.8 : focused ? 2.1 : 1.2,
              shadowBlur: selected ? 28 : focused ? 20 : 14,
              shadowColor: meta.color,
            },
            label: {
              opacity: dimmed ? 0.5 : 1,
            },
          }
        }),
        links: relationships.map((relationship) => {
          const touchesSelected = relationship.source_id === selectedNodeId || relationship.target_id === selectedNodeId
          const highlighted = !focusActive || (
            focusedNodeSet.has(relationship.source_id) && focusedNodeSet.has(relationship.target_id)
          )
          return {
            ...relationship,
            source: relationship.source_id,
            target: relationship.target_id,
            source_label: nodeNameMap.get(relationship.source_id) || relationship.source_id,
            target_label: nodeNameMap.get(relationship.target_id) || relationship.target_id,
            value: relationship.type,
            lineStyle: {
              color: RELATION_COLOR[relationship.type] || 'rgba(198, 206, 225, 0.46)',
              width: touchesSelected ? 3.1 : relationship.type === 'PROPOSES' ? 2.8 : 2,
              opacity: highlighted ? 0.84 : 0.22,
              curveness: relationship.type === 'USES' ? 0.18 : 0.12,
            },
            label: {
              show: false,
            },
          }
        }),
      },
    ],
  }
}

<script setup>
import { computed, ref, watch } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { GraphChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'

import {
  buildFilteredGraph,
  buildGraphCsvExport,
  buildGraphDegreeState,
  buildGraphHotspotRanking,
  buildGraphInsights,
  buildGraphJsonExport,
  buildGraphTableRows,
  buildGraphViewerOption,
  sortGraphLabels,
} from './graphViewerTransforms.js'

use([CanvasRenderer, GraphChart, TooltipComponent, LegendComponent])

const props = defineProps({
  summary: { type: Object, required: true },
  graphView: { type: Object, required: true },
  filters: { type: Object, required: true },
  selectedNode: { type: Object, default: null },
  selectedNodeId: { type: String, default: '' },
  viewBusy: { type: Boolean, default: false },
  expandBusy: { type: Boolean, default: false },
  expandingNodeId: { type: String, default: '' },
})

const emit = defineEmits(['refresh', 'select', 'expand', 'ask'])

const activeView = ref('graph')
const activeLabels = ref([])
const activeRelationTypes = ref([])
const paperQuery = ref('')
const sourceFilter = ref('all')
const focusMode = ref(false)
const sortBy = ref('degree')
const sortDirection = ref('desc')
const expandLimit = ref(24)

function normalizedText(value) {
  return String(value || '').trim()
}

function sortedEntries(object = {}, sorter = null) {
  const entries = Object.entries(object || {})
  return sorter ? entries.sort(sorter) : entries
}

function syncActiveValues(targetRef, nextOptions = [], sorter = null) {
  if (!nextOptions.length) {
    targetRef.value = []
    return
  }
  if (!targetRef.value.length) {
    targetRef.value = [...nextOptions]
    return
  }
  const nextActive = targetRef.value.filter((value) => nextOptions.includes(value))
  targetRef.value = nextActive.length ? (sorter ? [...nextActive].sort(sorter) : nextActive) : [...nextOptions]
}

function downloadText(filename, content, contentType) {
  if (!content) return
  const blob = new Blob([content], { type: contentType })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

const labelOptions = computed(() => sortGraphLabels(Object.keys(props.graphView.label_counts || {})))
const relationTypeOptions = computed(() =>
  Object.keys(props.graphView.relation_type_counts || {}).sort((left, right) =>
    String(left).localeCompare(String(right), 'en')
  )
)
const sourceOptions = computed(() =>
  [...new Set((props.graphView.nodes || []).map((node) => normalizedText(node.source)).filter(Boolean))]
    .sort((left, right) => left.localeCompare(right, 'zh-CN'))
)

watch(labelOptions, (labels) => {
  syncActiveValues(activeLabels, labels, (left, right) =>
    sortGraphLabels([left, right])[0] === left ? -1 : 1
  )
}, { immediate: true })

watch(relationTypeOptions, (types) => {
  syncActiveValues(activeRelationTypes, types, (left, right) =>
    String(left).localeCompare(String(right), 'en')
  )
}, { immediate: true })

const filteredGraph = computed(() => buildFilteredGraph(props.graphView, {
  labels: activeLabels.value,
  relationTypes: activeRelationTypes.value,
  paperQuery: paperQuery.value,
  source: sourceFilter.value,
  focusMode: focusMode.value,
  focusNodeId: props.selectedNodeId,
}))
const degreeState = computed(() => buildGraphDegreeState(filteredGraph.value))
const insights = computed(() => buildGraphInsights(filteredGraph.value))
const visibleLabelEntries = computed(() =>
  sortGraphLabels(Object.keys(filteredGraph.value.label_counts || {})).map((label) => [
    label,
    filteredGraph.value.label_counts[label],
  ])
)
const visibleRelationEntries = computed(() =>
  sortedEntries(filteredGraph.value.relation_type_counts, (left, right) => {
    if (right[1] !== left[1]) return right[1] - left[1]
    return String(left[0]).localeCompare(String(right[0]), 'en')
  })
)
const selectedNodeVisible = computed(() =>
  Boolean(props.selectedNodeId) && (filteredGraph.value.nodes || []).some((node) => node.id === props.selectedNodeId)
)
const selectedNodeMetrics = computed(() => ({
  degree: degreeState.value.degreeMap.get(props.selectedNodeId) || 0,
  inDegree: degreeState.value.inDegreeMap.get(props.selectedNodeId) || 0,
  outDegree: degreeState.value.outDegreeMap.get(props.selectedNodeId) || 0,
}))
const selectedRelations = computed(() => {
  if (!selectedNodeVisible.value) return []
  return (filteredGraph.value.relationships || []).filter((relationship) =>
    relationship.source_id === props.selectedNodeId || relationship.target_id === props.selectedNodeId
  )
})
const selectedNeighborRows = computed(() => {
  if (!selectedNodeVisible.value) return []
  const nodeMap = new Map((filteredGraph.value.nodes || []).map((node) => [node.id, node]))
  const neighbors = []
  for (const relationship of selectedRelations.value) {
    const neighborId = relationship.source_id === props.selectedNodeId
      ? relationship.target_id
      : relationship.source_id
    const node = nodeMap.get(neighborId)
    if (!node) continue
    neighbors.push({
      ...node,
      relation_type: relationship.type,
      degree: degreeState.value.degreeMap.get(neighborId) || 0,
    })
  }
  return neighbors
    .sort((left, right) => {
      if (right.degree !== left.degree) return right.degree - left.degree
      return normalizedText(left.name).localeCompare(normalizedText(right.name), 'zh-CN')
    })
    .slice(0, 8)
})
const tableRows = computed(() => buildGraphTableRows(filteredGraph.value, {
  sortBy: sortBy.value,
  sortDirection: sortDirection.value,
}))
const hotspotRows = computed(() => buildGraphHotspotRanking(filteredGraph.value, { limit: 8 }))
const hasPaperCoverage = computed(() => (insights.value.paperCount || 0) > 0)
const scopeSummary = computed(() =>
  hasPaperCoverage.value
    ? `${insights.value.paperCount || 0} 篇论文`
    : `${insights.value.topicCount || 0} 个主题`
)
const structureSummary = computed(() =>
  insights.value.componentCount > 1
    ? `${insights.value.componentCount} 个分量`
    : '单一主图'
)
const summaryCards = computed(() => ([
  {
    label: '当前覆盖',
    value: scopeSummary.value,
    desc: `来源 ${insights.value.sourceCount} 类，孤立节点 ${insights.value.isolatedNodeCount}`,
  },
  {
    label: '可见节点',
    value: String(insights.value.nodeCount || 0),
    desc: '当前筛选后保留的实体节点数',
  },
  {
    label: '可见关系',
    value: String(insights.value.relationshipCount || 0),
    desc: `连接密度 ${insights.value.densityText}`,
  },
  {
    label: '结构状态',
    value: structureSummary.value,
    desc: `平均连接 ${insights.value.averageDegreeText}，最大分量 ${insights.value.largestComponentSize}`,
  },
]))
const selectedQuestion = computed(() => {
  if (!props.selectedNode || !selectedNodeVisible.value) return ''
  const name = normalizedText(props.selectedNode.name)
  if (!name) return ''
  return hasPaperCoverage.value
    ? `${name} 在当前图谱里与哪些对象直接相关？`
    : `${name} 在当前图谱里关联了哪些策略、约束或接口？`
})
const chartOption = computed(() => buildGraphViewerOption(
  filteredGraph.value,
  selectedNodeVisible.value ? props.selectedNodeId : '',
  {
    degreeState: degreeState.value,
    focusedNodeIds: filteredGraph.value.focused_node_ids || [],
  },
))
const selectedFilterCount = computed(() => {
  let count = 0
  if (paperQuery.value.trim()) count += 1
  if (sourceFilter.value !== 'all') count += 1
  if (focusMode.value) count += 1
  if (activeLabels.value.length !== labelOptions.value.length) count += 1
  if (activeRelationTypes.value.length !== relationTypeOptions.value.length) count += 1
  return count
})

watch(selectedNodeVisible, (visible) => {
  if (!visible) {
    focusMode.value = false
  }
})

function handleRefresh() {
  emit('refresh')
}

function handleSelect(nodeId = '') {
  emit('select', nodeId)
}

function handleExpand(nodeId = '', limit = expandLimit.value) {
  const normalizedNodeId = normalizedText(nodeId || props.selectedNodeId)
  if (!normalizedNodeId || props.viewBusy || props.expandBusy) return
  emit('expand', normalizedNodeId, Number(limit || expandLimit.value || 24))
}

function handleAskSample(question = '') {
  const normalizedQuestion = normalizedText(question)
  if (!normalizedQuestion) return
  emit('ask', normalizedQuestion)
}

function handleChartClick(params) {
  if (params?.dataType !== 'node') return
  handleSelect(params.data?.id || '')
}

function handleChartDblClick(params) {
  if (params?.dataType !== 'node') return
  const nodeId = params.data?.id || ''
  handleSelect(nodeId)
  handleExpand(nodeId)
}

function onSearchKeydown(event) {
  if (event.key !== 'Enter') return
  event.preventDefault()
  handleRefresh()
}

function toggleLabel(label) {
  if (activeLabels.value.includes(label)) {
    if (activeLabels.value.length === 1) return
    activeLabels.value = activeLabels.value.filter((item) => item !== label)
    return
  }
  activeLabels.value = sortGraphLabels([...activeLabels.value, label])
}

function toggleRelationType(type) {
  if (activeRelationTypes.value.includes(type)) {
    if (activeRelationTypes.value.length === 1) return
    activeRelationTypes.value = activeRelationTypes.value.filter((item) => item !== type)
    return
  }
  activeRelationTypes.value = [...activeRelationTypes.value, type].sort((left, right) =>
    String(left).localeCompare(String(right), 'en')
  )
}

function resetLocalFilters() {
  activeLabels.value = [...labelOptions.value]
  activeRelationTypes.value = [...relationTypeOptions.value]
  paperQuery.value = ''
  sourceFilter.value = 'all'
  focusMode.value = false
  sortBy.value = 'degree'
  sortDirection.value = 'desc'
  expandLimit.value = 24
  activeView.value = 'graph'
}

function downloadVisibleGraphJson() {
  downloadText(
    'graph-view.json',
    buildGraphJsonExport(filteredGraph.value),
    'application/json;charset=utf-8',
  )
}

function downloadVisibleTableCsv() {
  downloadText(
    'graph-view.csv',
    buildGraphCsvExport(tableRows.value),
    'text/csv;charset=utf-8',
  )
}
</script>

<template>
  <section class="graph-catalog tech-card">
    <div class="graph-catalog__head">
      <div>
        <div class="graph-catalog__eyebrow">图谱展示</div>
        <div class="graph-catalog__title">图谱分析台</div>
        <div class="graph-catalog__subtitle">
          用一块分析台完成检索、筛选、节点展开和结构查看，把原来冗余的说明块收回到真正需要操作的信息上。
        </div>
      </div>
      <div class="ink-inline-meta">
        <span class="status-badge" :class="props.summary.neo4j_connected ? 'status-badge--ok' : 'status-badge--warning'">
          {{ props.summary.neo4j_connected ? '图库在线' : '图库离线' }}
        </span>
        <span class="status-badge">
          {{ scopeSummary }}
        </span>
        <span class="status-badge" v-if="selectedFilterCount">
          本地过滤 {{ selectedFilterCount }} 项
        </span>
      </div>
    </div>

    <div class="graph-catalog__overview">
      <article
        v-for="(card, index) in summaryCards"
        :key="card.label"
        class="graph-catalog__overview-card"
        :class="{ 'graph-catalog__overview-card--accent': index === 0 }"
      >
        <div class="graph-catalog__overview-label">{{ card.label }}</div>
        <div class="graph-catalog__overview-value">{{ card.value }}</div>
        <div class="graph-catalog__overview-desc">{{ card.desc }}</div>
      </article>
    </div>

    <div class="graph-catalog__toolbar">
      <div class="graph-catalog__toolbar-fields">
        <label class="graph-catalog__search">
          <span>服务端搜索</span>
          <input
            v-model="props.filters.query"
            type="text"
            :placeholder="hasPaperCoverage ? '按论文名、方法名、任务名搜索' : '按主题名、策略名、约束名搜索'"
            @keydown="onSearchKeydown"
          />
        </label>
        <label class="graph-catalog__limit">
          <span>加载上限</span>
          <select v-model.number="props.filters.limit">
            <option :value="24">24</option>
            <option :value="40">40</option>
            <option :value="60">60</option>
            <option :value="90">90</option>
            <option :value="120">120</option>
          </select>
        </label>
      </div>
      <div class="graph-catalog__toolbar-actions">
        <button
          class="btn-tech"
          :class="{ 'btn-tech--primary': activeView === 'graph' }"
          @click="activeView = 'graph'"
        >
          关系图
        </button>
        <button
          class="btn-tech"
          :class="{ 'btn-tech--primary': activeView === 'table' }"
          @click="activeView = 'table'"
        >
          数据表
        </button>
        <button class="btn-tech" :disabled="props.viewBusy || props.expandBusy" @click="handleRefresh">
          {{ props.viewBusy ? '刷新中...' : '刷新视图' }}
        </button>
        <button class="btn-tech" :disabled="!filteredGraph.nodes.length" @click="downloadVisibleGraphJson">
          导出 JSON
        </button>
        <button class="btn-tech" :disabled="!tableRows.length" @click="downloadVisibleTableCsv">
          导出 CSV
        </button>
      </div>
    </div>

    <div class="graph-catalog__controls">
      <div class="graph-catalog__controls-grid">
        <label class="graph-catalog__control">
          <span>{{ hasPaperCoverage ? '本地检索' : '主题检索' }}</span>
          <input v-model="paperQuery" type="text" :placeholder="hasPaperCoverage ? '按论文标题、节点名或描述过滤当前视图' : '按主题标题、节点名或描述过滤当前视图'" />
        </label>

        <label class="graph-catalog__control">
          <span>来源过滤</span>
          <select v-model="sourceFilter">
            <option value="all">全部来源</option>
            <option v-for="source in sourceOptions" :key="source" :value="source">{{ source }}</option>
          </select>
        </label>

        <label class="graph-catalog__control">
          <span>排序字段</span>
          <select v-model="sortBy">
            <option value="degree">总连接数</option>
            <option value="name">节点名称</option>
            <option value="label">节点标签</option>
            <option value="paper_title">所属主题</option>
            <option value="source">来源</option>
            <option value="in_degree">入边数</option>
            <option value="out_degree">出边数</option>
          </select>
        </label>

        <label class="graph-catalog__control">
          <span>排序方向</span>
          <select v-model="sortDirection">
            <option value="desc">降序</option>
            <option value="asc">升序</option>
          </select>
        </label>

        <label class="graph-catalog__control">
          <span>展开上限</span>
          <select v-model.number="expandLimit">
            <option :value="12">12</option>
            <option :value="24">24</option>
            <option :value="40">40</option>
            <option :value="60">60</option>
          </select>
        </label>

        <div class="graph-catalog__control graph-catalog__control--actions">
          <span>探索操作</span>
          <div class="graph-catalog__control-actions">
            <button
              class="btn-tech"
              :disabled="!selectedNodeVisible"
              :class="{ 'btn-tech--primary': focusMode }"
              @click="focusMode = !focusMode"
            >
              {{ focusMode ? '取消聚焦' : '聚焦当前节点' }}
            </button>
            <button class="btn-tech" @click="resetLocalFilters">重置筛选</button>
          </div>
        </div>
      </div>
    </div>

    <div class="graph-catalog__filter-grid">
      <div class="graph-catalog__filter-card">
        <div class="graph-catalog__filter-head">
          <span>标签过滤</span>
          <span class="graph-catalog__filter-meta">{{ activeLabels.length }} / {{ labelOptions.length }}</span>
        </div>
        <div class="graph-catalog__chips">
          <button
            v-for="label in labelOptions"
            :key="label"
            class="graph-catalog__chip graph-catalog__chip--filter"
            :class="{ 'graph-catalog__chip--active': activeLabels.includes(label), 'graph-catalog__chip--inactive': !activeLabels.includes(label) }"
            @click="toggleLabel(label)"
          >
            {{ label }} · {{ props.graphView.label_counts?.[label] || 0 }}
          </button>
          <span v-if="!labelOptions.length" class="graph-catalog__chip graph-catalog__chip--muted">暂无节点标签</span>
        </div>
      </div>

      <div class="graph-catalog__filter-card">
        <div class="graph-catalog__filter-head">
          <span>关系过滤</span>
          <span class="graph-catalog__filter-meta">{{ activeRelationTypes.length }} / {{ relationTypeOptions.length }}</span>
        </div>
        <div class="graph-catalog__chips">
          <button
            v-for="type in relationTypeOptions"
            :key="type"
            class="graph-catalog__chip graph-catalog__chip--filter graph-catalog__chip--relation"
            :class="{ 'graph-catalog__chip--active': activeRelationTypes.includes(type), 'graph-catalog__chip--inactive': !activeRelationTypes.includes(type) }"
            @click="toggleRelationType(type)"
          >
            {{ type }} · {{ props.graphView.relation_type_counts?.[type] || 0 }}
          </button>
          <span v-if="!relationTypeOptions.length" class="graph-catalog__chip graph-catalog__chip--muted">暂无关系类型</span>
        </div>
      </div>
    </div>

    <div v-if="!props.summary.neo4j_connected" class="graph-catalog__empty">
      <div class="graph-catalog__empty-title">图库当前未连接</div>
      <div class="graph-catalog__empty-text">先回到“知识入图”确认 Neo4j 已连接，再回来查看关系结构和节点分析结果。</div>
    </div>

    <div v-else-if="!(props.graphView.nodes || []).length" class="graph-catalog__empty">
      <div class="graph-catalog__empty-title">当前还没有可分析的图谱数据</div>
      <div class="graph-catalog__empty-text">先在“知识入图”写入 Neo4j，或点击“刷新视图”重新拉取服务端图谱内容。</div>
    </div>

    <div v-else-if="!filteredGraph.nodes.length" class="graph-catalog__empty">
      <div class="graph-catalog__empty-title">当前筛选结果为空</div>
      <div class="graph-catalog__empty-text">本地过滤已经把所有节点排除了。放宽标签、关系或来源条件，或者直接重置筛选后再查看。</div>
    </div>

    <div v-else class="graph-catalog__layout">
      <div class="graph-catalog__canvas">
        <div class="graph-catalog__canvas-head">
          <div>
            <div class="graph-catalog__canvas-title">{{ activeView === 'graph' ? '关系视图' : '节点数据表' }}</div>
            <div class="graph-catalog__canvas-tip">
              {{
                activeView === 'graph'
                  ? '单击节点查看详情，双击节点可按当前上限继续展开邻居。'
                  : '表格按当前排序规则展示节点，适合快速定位热点实体和来源。'
              }}
            </div>
          </div>
          <div class="ink-inline-meta">
            <span class="status-badge">{{ insights.nodeCount }} 节点</span>
            <span class="status-badge">{{ insights.relationshipCount }} 关系</span>
          </div>
        </div>

        <div class="graph-catalog__meta-grid">
          <div class="graph-catalog__meta-card">
            <span>标签分布</span>
            <div class="graph-catalog__chips">
              <span
                v-for="[label, count] in visibleLabelEntries"
                :key="label"
                class="graph-catalog__chip graph-catalog__chip--active"
              >
                {{ label }} · {{ count }}
              </span>
            </div>
          </div>
          <div class="graph-catalog__meta-card">
            <span>关系分布</span>
            <div class="graph-catalog__chips">
              <span
                v-for="[type, count] in visibleRelationEntries"
                :key="type"
                class="graph-catalog__chip graph-catalog__chip--relation"
              >
                {{ type }} · {{ count }}
              </span>
            </div>
          </div>
        </div>

        <v-chart
          v-if="activeView === 'graph'"
          class="graph-catalog__chart"
          :option="chartOption"
          autoresize
          @click="handleChartClick"
          @dblclick="handleChartDblClick"
        />

        <div v-else class="graph-catalog__table-wrap">
          <table class="graph-catalog__table">
            <thead>
              <tr>
                <th>节点</th>
                <th>标签</th>
                <th>所属主题</th>
                <th>来源</th>
                <th>总连接</th>
                <th>入边</th>
                <th>出边</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in tableRows"
                :key="row.id"
                :class="{ 'graph-catalog__table-row--active': row.id === props.selectedNodeId }"
                @click="handleSelect(row.id)"
              >
                <td>
                  <div class="graph-table__name">{{ row.name }}</div>
                  <div v-if="row.description_preview" class="graph-table__desc">{{ row.description_preview }}</div>
                </td>
                <td>{{ row.label }}</td>
                <td>{{ row.paper_title || '-' }}</td>
                <td>{{ row.source || '-' }}</td>
                <td>{{ row.degree }}</td>
                <td>{{ row.in_degree }}</td>
                <td>{{ row.out_degree }}</td>
                <td>
                  <button class="btn-tech" :disabled="props.expandBusy" @click.stop="handleExpand(row.id)">
                    {{ props.expandBusy && props.expandingNodeId === row.id ? '展开中...' : '扩邻居' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <aside class="graph-catalog__inspector">
        <div class="graph-catalog__inspector-card">
          <div class="graph-catalog__inspector-top">
            <div>
              <div class="graph-catalog__inspector-label">节点检查器</div>
              <div class="graph-catalog__inspector-tip">查看当前节点的标签、来源、描述和连边情况。</div>
            </div>
            <div class="graph-catalog__inspector-actions" v-if="props.selectedNode && selectedNodeVisible">
              <button
                class="btn-tech"
                :disabled="props.viewBusy || props.expandBusy"
                @click="handleExpand(props.selectedNodeId)"
              >
                {{
                  props.expandBusy && props.expandingNodeId === props.selectedNodeId
                    ? '展开中...'
                    : `展开邻居 (${expandLimit})`
                }}
              </button>
              <button
                v-if="selectedQuestion"
                class="btn-tech"
                @click="handleAskSample(selectedQuestion)"
              >
                转到问答台
              </button>
            </div>
          </div>

          <div v-if="props.selectedNode && selectedNodeVisible" class="graph-node">
            <div class="graph-node__title">{{ props.selectedNode.name }}</div>
            <div class="graph-node__badges">
              <span class="status-badge status-badge--ok">{{ props.selectedNode.label }}</span>
              <span v-if="props.selectedNode.source" class="status-badge">{{ props.selectedNode.source }}</span>
            </div>
            <div class="graph-node__stats">
              <span class="graph-node__stat">总连接 {{ selectedNodeMetrics.degree }}</span>
              <span class="graph-node__stat">入边 {{ selectedNodeMetrics.inDegree }}</span>
              <span class="graph-node__stat">出边 {{ selectedNodeMetrics.outDegree }}</span>
            </div>
            <div v-if="props.selectedNode.paper_title" class="graph-node__meta">
              所属主题：{{ props.selectedNode.paper_title }}
            </div>
            <div v-if="props.selectedNode.description" class="graph-node__desc">
              {{ props.selectedNode.description }}
            </div>
          </div>
          <div v-else-if="props.selectedNode" class="graph-node__empty">
            当前节点已被本地过滤隐藏。放宽标签、来源或聚焦条件后会恢复展示。
          </div>
          <div v-else class="graph-node__empty">
            先在关系图或数据表中选中一个节点，这里会显示它的摘要和邻接信息。
          </div>
        </div>

        <div class="graph-catalog__inspector-card">
          <div class="graph-catalog__inspector-top">
            <div class="graph-catalog__inspector-label">邻居预览</div>
            <div class="graph-catalog__inspector-tip">{{ selectedNeighborRows.length }} 项</div>
          </div>
          <div v-if="selectedNeighborRows.length" class="graph-neighbors">
            <button
              v-for="neighbor in selectedNeighborRows"
              :key="neighbor.id"
              class="graph-neighbors__item"
              @click="handleSelect(neighbor.id)"
            >
              <span class="graph-neighbors__name">{{ neighbor.name }}</span>
              <span class="graph-neighbors__meta">{{ neighbor.label }} · {{ neighbor.relation_type }} · {{ neighbor.degree }}</span>
            </button>
          </div>
          <div v-else class="graph-node__empty">
            当前节点在当前视图下没有可见邻居。
          </div>
        </div>

        <div class="graph-catalog__inspector-card">
          <div class="graph-catalog__inspector-top">
            <div class="graph-catalog__inspector-label">热点实体</div>
            <div class="graph-catalog__inspector-tip">Top 8</div>
          </div>
          <div v-if="hotspotRows.length" class="graph-ranking">
            <button
              v-for="row in hotspotRows"
              :key="row.id"
              class="graph-ranking__item"
              @click="handleSelect(row.id)"
            >
              <span class="graph-ranking__index">#{{ row.rank }}</span>
              <span class="graph-ranking__main">
                <span class="graph-ranking__name">{{ row.name }}</span>
                <span class="graph-ranking__meta">{{ row.label }} · {{ row.degree }} 连接</span>
              </span>
            </button>
          </div>
          <div v-else class="graph-node__empty">
            当前视图还没有足够的热点节点可展示。
          </div>
        </div>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.graph-catalog {
  padding: 22px 24px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.graph-catalog__head,
.graph-catalog__toolbar,
.graph-catalog__toolbar-actions,
.graph-catalog__filter-head,
.graph-catalog__canvas-head,
.graph-catalog__inspector-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.graph-catalog__eyebrow {
  font-size: 0.72rem;
  letter-spacing: 0.16em;
  color: var(--text-muted);
  text-transform: uppercase;
}

.graph-catalog__title {
  margin-top: 8px;
  font-size: 1.18rem;
  font-weight: 700;
  color: var(--text-primary);
}

.graph-catalog__subtitle {
  margin-top: 8px;
  max-width: 760px;
  font-size: 0.8rem;
  color: var(--text-secondary);
  line-height: 1.8;
}

.graph-catalog__toolbar {
  align-items: end;
  flex-wrap: wrap;
}

.graph-catalog__toolbar-fields {
  display: flex;
  gap: 12px;
  flex: 1;
  min-width: 0;
  align-items: end;
}

.graph-catalog__search,
.graph-catalog__limit,
.graph-catalog__control {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.graph-catalog__search {
  flex: 1;
}

.graph-catalog__limit {
  width: 132px;
}

.graph-catalog__toolbar-actions,
.graph-catalog__control-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.graph-catalog__controls,
.graph-catalog__filter-card,
.graph-catalog__overview-card,
.graph-catalog__meta-card,
.graph-catalog__canvas,
.graph-catalog__inspector-card {
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  box-shadow: var(--shadow-card);
}

.graph-catalog__controls-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.graph-catalog__control span,
.graph-catalog__search span,
.graph-catalog__limit span,
.graph-catalog__filter-head span,
.graph-catalog__filter-meta,
.graph-catalog__inspector-label,
.graph-catalog__canvas-title {
  font-size: 0.76rem;
  color: var(--text-muted);
}

.graph-catalog__control--actions {
  justify-content: space-between;
}

.graph-catalog__overview {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.graph-catalog__overview-label {
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  color: var(--text-muted);
}

.graph-catalog__overview-value {
  margin-top: 10px;
  font-size: 1.32rem;
  font-weight: 700;
  color: var(--text-primary);
}

.graph-catalog__overview-desc {
  margin-top: 8px;
  font-size: 0.74rem;
  color: var(--text-secondary);
  line-height: 1.7;
}

.graph-catalog__overview-card:nth-child(1),
.graph-catalog__overview-card--accent {
  background: var(--state-ok-bg);
}

.graph-catalog__overview-card:nth-child(2) {
  background: var(--bg-surface);
}

.graph-catalog__overview-card:nth-child(3) {
  background: var(--bg-surface);
}

.graph-catalog__filter-grid,
.graph-catalog__meta-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.graph-catalog__chips {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.graph-catalog__chip {
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border-radius: 999px;
  background: var(--state-ok-bg);
  color: var(--text-secondary);
  font-size: 0.72rem;
  line-height: 1;
  border: 1px solid var(--state-ok-border);
}

.graph-catalog__chip--filter {
  cursor: pointer;
  transition: transform 0.2s ease, border-color 0.2s ease, background 0.2s ease;
}

.graph-catalog__chip--filter:hover {
  transform: translateY(-1px);
  border-color: var(--border-strong);
}

.graph-catalog__chip--active {
  color: var(--text-primary);
  border-color: var(--state-ok-border);
  background: var(--state-ok-bg);
}

.graph-catalog__chip--relation {
  background: var(--bg-surface);
  border-color: var(--border-color);
}

.graph-catalog__chip--relation.graph-catalog__chip--active {
  color: var(--text-primary);
  border-color: var(--state-ok-border);
  background: var(--state-ok-bg);
}

.graph-catalog__chip--source {
  background: var(--bg-surface);
  border-color: var(--border-color);
}

.graph-catalog__chip--inactive {
  background: var(--bg-surface);
  color: var(--text-muted);
  border-color: var(--border-color);
}

.graph-catalog__chip--muted {
  background: var(--bg-surface);
  color: var(--text-muted);
  border-color: var(--border-color);
}

.graph-catalog__empty,
.graph-node__empty {
  padding: 18px;
  border-radius: 16px;
  border: 1px dashed var(--border-color);
  color: var(--text-muted);
  line-height: 1.8;
}

.graph-catalog__empty {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.graph-catalog__empty-title {
  color: var(--text-primary);
  font-size: 0.92rem;
  font-weight: 700;
}

.graph-catalog__empty-text {
  color: var(--text-secondary);
  font-size: 0.78rem;
  line-height: 1.8;
}

.graph-catalog__layout {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(320px, 0.7fr);
  gap: 16px;
  align-items: start;
}

.graph-catalog__canvas-title {
  color: var(--text-primary);
  font-weight: 600;
}

.graph-catalog__canvas-tip {
  margin-top: 6px;
  font-size: 0.76rem;
  color: var(--text-secondary);
  line-height: 1.8;
}

.graph-catalog__chart {
  width: 100%;
  height: 660px;
  margin-top: 12px;
}

.graph-catalog__table-wrap {
  margin-top: 12px;
  max-height: 660px;
  overflow: auto;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: var(--bg-surface);
}

.graph-catalog__table {
  width: 100%;
  min-width: 920px;
  border-collapse: collapse;
}

.graph-catalog__table th,
.graph-catalog__table td {
  padding: 12px 14px;
  text-align: left;
  border-bottom: 1px solid var(--border-color);
  font-size: 0.76rem;
  color: var(--text-secondary);
  vertical-align: top;
}

.graph-catalog__table th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: var(--bg-strong);
  color: var(--text-muted);
}

.graph-catalog__table tbody tr {
  cursor: pointer;
  transition: background 0.2s ease;
}

.graph-catalog__table tbody tr:hover,
.graph-catalog__table-row--active {
  background: var(--state-ok-bg);
}

.graph-table__name,
.graph-node__title {
  font-size: 0.84rem;
  font-weight: 700;
  color: var(--text-primary);
}

.graph-table__desc,
.graph-node__meta,
.graph-node__desc {
  margin-top: 6px;
  font-size: 0.74rem;
  color: var(--text-secondary);
  line-height: 1.75;
}

.graph-catalog__inspector {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.graph-catalog__inspector-tip {
  margin-top: 6px;
  font-size: 0.74rem;
  line-height: 1.7;
  color: var(--text-secondary);
}

.graph-catalog__inspector-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.graph-node__badges,
.graph-node__stats {
  margin-top: 10px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.graph-node__stat {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: 0.72rem;
}

.graph-neighbors,
.graph-ranking {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.graph-neighbors__item,
.graph-ranking__item {
  width: 100%;
  padding: 10px 12px;
  display: flex;
  align-items: center;
  gap: 10px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background: var(--bg-surface);
  text-align: left;
  cursor: pointer;
  transition: transform 0.2s ease, border-color 0.2s ease, background 0.2s ease;
}

.graph-neighbors__item:hover,
.graph-ranking__item:hover {
  transform: translateY(-1px);
  border-color: var(--border-strong);
  background: var(--bg-card-hover);
}

.graph-neighbors__item {
  flex-direction: column;
  align-items: flex-start;
}

.graph-neighbors__name,
.graph-ranking__name {
  font-size: 0.8rem;
  color: var(--text-primary);
  font-weight: 600;
}

.graph-neighbors__meta,
.graph-ranking__meta {
  font-size: 0.72rem;
  color: var(--text-muted);
}

.graph-ranking__index {
  min-width: 36px;
  font-size: 0.78rem;
  color: var(--accent-primary);
  font-weight: 700;
}

.graph-ranking__main {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

@media (max-width: 1280px) {
  .graph-catalog__overview {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .graph-catalog__controls-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 1100px) {
  .graph-catalog__layout,
  .graph-catalog__filter-grid,
  .graph-catalog__meta-grid {
    grid-template-columns: 1fr;
  }

  .graph-catalog__chart {
    height: 520px;
  }

  .graph-catalog__table {
    min-width: 760px;
  }
}

@media (max-width: 860px) {
  .graph-catalog {
    padding: 18px;
  }

  .graph-catalog__head,
  .graph-catalog__toolbar,
  .graph-catalog__toolbar-fields,
  .graph-catalog__toolbar-actions,
  .graph-catalog__filter-head,
  .graph-catalog__canvas-head,
  .graph-catalog__inspector-top,
  .graph-catalog__inspector-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .graph-catalog__overview,
  .graph-catalog__controls-grid {
    grid-template-columns: 1fr;
  }

  .graph-catalog__chart {
    height: 440px;
  }
}
</style>

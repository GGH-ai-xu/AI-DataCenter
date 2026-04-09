<script setup>
import { computed, ref, watch } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { GraphChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'

import {
  buildGraphDefenseOverview,
  buildFilteredGraph,
  buildGraphCsvExport,
  buildGraphDegreeState,
  buildGraphHotspotRanking,
  buildGraphInsights,
  buildGraphJsonExport,
  buildGraphPaperGroups,
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
const sourceEntries = computed(() => {
  const counts = {}
  for (const node of props.graphView.nodes || []) {
    const source = normalizedText(node.source)
    if (!source) continue
    counts[source] = (counts[source] || 0) + 1
  }
  return sortedEntries(counts, (left, right) => String(left[0]).localeCompare(String(right[0]), 'zh-CN'))
})

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
  sortedEntries(filteredGraph.value.relation_type_counts, (left, right) =>
    String(left[0]).localeCompare(String(right[0]), 'en')
  )
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
const paperGroups = computed(() => buildGraphPaperGroups(filteredGraph.value, { limit: 6 }))
const defenseOverview = computed(() => buildGraphDefenseOverview(filteredGraph.value))
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
        <div class="graph-catalog__eyebrow">Presentation Board</div>
        <div class="graph-catalog__title">知识图谱答辩展示台</div>
        <div class="graph-catalog__subtitle">
          用一张图把“论文提出了什么、建立在什么之上、解决了什么任务、落在什么指标上”讲清楚。
        </div>
      </div>
      <div class="ink-inline-meta">
        <span class="status-badge" :class="props.summary.neo4j_connected ? 'status-badge--ok' : 'status-badge--warning'">
          {{ props.summary.neo4j_connected ? '图库在线' : '图库离线' }}
        </span>
        <span class="status-badge">
          {{ filteredGraph.nodes.length }} / {{ props.graphView.nodes?.length || 0 }} 节点
        </span>
        <span class="status-badge" v-if="selectedFilterCount">
          本地过滤 {{ selectedFilterCount }} 项
        </span>
        <span class="status-badge" v-if="defenseOverview.answerReadyNotes?.length">
          可直接答辩
        </span>
      </div>
    </div>

    <section class="graph-defense">
      <div class="graph-defense__hero">
        <div class="graph-defense__eyebrow">开场总结</div>
        <div class="graph-defense__headline">{{ defenseOverview.headline }}</div>
        <div class="graph-defense__subline">{{ defenseOverview.subline }}</div>
        <div class="graph-defense__hero-meta">
          <span
            v-for="note in defenseOverview.answerReadyNotes"
            :key="note"
            class="graph-defense__hero-chip"
          >
            {{ note }}
          </span>
        </div>
      </div>

      <div class="graph-defense__cards">
        <article
          v-for="card in defenseOverview.focusCards"
          :key="card.label"
          class="graph-defense__card"
        >
          <div class="graph-defense__card-label">{{ card.label }}</div>
          <div class="graph-defense__card-value">{{ card.value }}</div>
          <div class="graph-defense__card-detail">{{ card.detail }}</div>
        </article>
      </div>

      <div class="graph-defense__tracks">
        <article class="graph-defense__track">
          <div class="graph-defense__track-head">答辩讲解线</div>
          <div class="graph-defense__track-body">
            <div
              v-for="(point, index) in defenseOverview.talkingPoints"
              :key="`${index}-${point}`"
              class="graph-defense__point"
            >
              <span class="graph-defense__point-index">{{ index + 1 }}</span>
              <span>{{ point }}</span>
            </div>
          </div>
        </article>

        <article class="graph-defense__track">
          <div class="graph-defense__track-head">建议演示顺序</div>
          <div class="graph-defense__track-body">
            <div
              v-for="(step, index) in defenseOverview.presentationFlow"
              :key="`${index}-${step}`"
              class="graph-defense__step"
            >
              <span class="graph-defense__step-index">Step {{ index + 1 }}</span>
              <span>{{ step }}</span>
            </div>
          </div>
        </article>

        <article class="graph-defense__track">
          <div class="graph-defense__track-head">评委可追问</div>
          <div class="graph-defense__track-body graph-defense__track-body--questions">
            <button
              v-for="question in defenseOverview.judgeQuestions"
              :key="question"
              class="graph-defense__question"
              @click="handleAskSample(question)"
            >
              {{ question }}
            </button>
          </div>
        </article>
      </div>
    </section>

    <div class="graph-catalog__toolbar">
      <label class="graph-catalog__search">
        <span>服务端搜索</span>
        <input
          v-model="props.filters.query"
          type="text"
          placeholder="按论文名、方法名、任务名搜索"
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
      <div class="graph-catalog__toolbar-actions">
        <button class="btn-tech" :disabled="props.viewBusy || props.expandBusy" @click="handleRefresh">
          {{ props.viewBusy ? '刷新中...' : '刷新图库' }}
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
          <span>本地论文检索</span>
          <input v-model="paperQuery" type="text" placeholder="按 paper_title / 描述二次过滤当前视图" />
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
            <option value="paper_title">所属论文</option>
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
          <span>展开邻居上限</span>
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
              :class="{ 'btn-tech--primary': activeView === 'graph' }"
              @click="activeView = 'graph'"
            >
              图谱视图
            </button>
            <button
              class="btn-tech"
              :class="{ 'btn-tech--primary': activeView === 'table' }"
              @click="activeView = 'table'"
            >
              表格视图
            </button>
            <button
              class="btn-tech"
              :disabled="!selectedNodeVisible"
              :class="{ 'btn-tech--primary': focusMode }"
              @click="focusMode = !focusMode"
            >
              {{ focusMode ? '取消聚焦' : '聚焦当前节点' }}
            </button>
            <button class="btn-tech" @click="resetLocalFilters">重置本地过滤</button>
          </div>
        </div>
      </div>
    </div>

    <div class="graph-catalog__overview">
      <div class="graph-catalog__overview-card">
        <div class="graph-catalog__overview-label">可见节点</div>
        <div class="graph-catalog__overview-value">{{ insights.nodeCount }}</div>
        <div class="graph-catalog__overview-desc">当前视图保留的实体节点数</div>
      </div>
      <div class="graph-catalog__overview-card">
        <div class="graph-catalog__overview-label">可见关系</div>
        <div class="graph-catalog__overview-value">{{ insights.relationshipCount }}</div>
        <div class="graph-catalog__overview-desc">当前筛选后仍保留的连接</div>
      </div>
      <div class="graph-catalog__overview-card">
        <div class="graph-catalog__overview-label">平均连接度</div>
        <div class="graph-catalog__overview-value">{{ insights.averageDegreeText }}</div>
        <div class="graph-catalog__overview-desc">每个节点平均关联的边数</div>
      </div>
      <div class="graph-catalog__overview-card">
        <div class="graph-catalog__overview-label">连接密度</div>
        <div class="graph-catalog__overview-value">{{ insights.densityText }}</div>
        <div class="graph-catalog__overview-desc">关系覆盖程度，适合现场解释图谱结构</div>
      </div>
      <div class="graph-catalog__overview-card">
        <div class="graph-catalog__overview-label">连通分量</div>
        <div class="graph-catalog__overview-value">{{ insights.componentCount }}</div>
        <div class="graph-catalog__overview-desc">最大分量 {{ insights.largestComponentSize }} 个节点</div>
      </div>
      <div class="graph-catalog__overview-card">
        <div class="graph-catalog__overview-label">论文覆盖</div>
        <div class="graph-catalog__overview-value">{{ insights.paperCount }}</div>
        <div class="graph-catalog__overview-desc">来源 {{ insights.sourceCount }} 类，孤立节点 {{ insights.isolatedNodeCount }}</div>
      </div>
    </div>

    <div class="graph-catalog__filter-grid">
      <div class="graph-catalog__filter-card">
        <div class="graph-catalog__filter-head">
          <span>标签过滤</span>
          <button class="btn-tech" :disabled="!labelOptions.length" @click="activeLabels = [...labelOptions]">全部显示</button>
        </div>
        <div class="graph-catalog__chips">
          <button
            v-for="label in labelOptions"
            :key="label"
            class="graph-catalog__chip graph-catalog__chip--filter"
            :class="{ 'graph-catalog__chip--inactive': !activeLabels.includes(label) }"
            @click="toggleLabel(label)"
          >
            {{ label }} · {{ props.graphView.label_counts?.[label] || 0 }}
          </button>
          <span v-if="!labelOptions.length" class="graph-catalog__chip graph-catalog__chip--muted">暂无节点</span>
        </div>
      </div>

      <div class="graph-catalog__filter-card">
        <div class="graph-catalog__filter-head">
          <span>关系过滤</span>
          <button class="btn-tech" :disabled="!relationTypeOptions.length" @click="activeRelationTypes = [...relationTypeOptions]">全部显示</button>
        </div>
        <div class="graph-catalog__chips">
          <button
            v-for="type in relationTypeOptions"
            :key="type"
            class="graph-catalog__chip graph-catalog__chip--filter graph-catalog__chip--relation"
            :class="{ 'graph-catalog__chip--inactive': !activeRelationTypes.includes(type) }"
            @click="toggleRelationType(type)"
          >
            {{ type }} · {{ props.graphView.relation_type_counts?.[type] || 0 }}
          </button>
          <span v-if="!relationTypeOptions.length" class="graph-catalog__chip graph-catalog__chip--muted">暂无关系</span>
        </div>
      </div>
    </div>

    <div v-if="sourceEntries.length" class="graph-catalog__source-panel">
      <div class="graph-catalog__filter-head">
        <span>来源分布</span>
      </div>
      <div class="graph-catalog__chips">
        <span
          v-for="[source, count] in sourceEntries"
          :key="source"
          class="graph-catalog__chip graph-catalog__chip--source"
        >
          {{ source }} · {{ count }}
        </span>
      </div>
    </div>

    <div v-if="!props.summary.neo4j_connected" class="graph-catalog__empty">
      Neo4j 当前未连接。请先重连图库，再刷新视图。
    </div>

    <div v-else-if="!(props.graphView.nodes || []).length" class="graph-catalog__empty">
      当前搜索结果为空。可以先导入论文，或清空搜索词后重新刷新图库。
    </div>

    <div v-else-if="!filteredGraph.nodes.length" class="graph-catalog__empty">
      当前本地过滤把节点全部筛空了。你可以重置过滤，或重新勾选标签 / 关系类型。
    </div>

    <div v-else class="graph-catalog__layout">
      <div class="graph-catalog__canvas">
        <div class="graph-catalog__canvas-head">
          <div>
            <div class="graph-catalog__canvas-title">{{ activeView === 'graph' ? '图谱沙盘' : '节点表格' }}</div>
            <div class="graph-catalog__canvas-tip">
              {{
                activeView === 'graph'
                  ? '单击节点看详情，双击节点扩邻居。节点大小与连接度相关，聚焦模式会保留当前节点及其一跳邻居。'
                  : '表格适合答辩时展示“有哪些节点、属于哪篇论文、连接度如何”，支持排序和导出。'
              }}
            </div>
          </div>
          <div class="ink-inline-meta">
            <span class="status-badge">{{ visibleLabelEntries.length }} 类节点</span>
            <span class="status-badge">{{ visibleRelationEntries.length }} 类关系</span>
          </div>
        </div>

        <div class="graph-catalog__meta-grid">
          <div class="graph-catalog__meta-card">
            <span>当前视图标签</span>
            <div class="graph-catalog__chips">
              <span
                v-for="[label, count] in visibleLabelEntries"
                :key="label"
                class="graph-catalog__chip"
              >
                {{ label }} · {{ count }}
              </span>
            </div>
          </div>
          <div class="graph-catalog__meta-card">
            <span>当前视图关系</span>
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
                <th>所属论文</th>
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
            <div class="graph-catalog__inspector-label">当前节点</div>
            <button
              v-if="props.selectedNode && selectedNodeVisible"
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
              所属论文：{{ props.selectedNode.paper_title }}
            </div>
            <div v-if="props.selectedNode.description" class="graph-node__desc">
              {{ props.selectedNode.description }}
            </div>
          </div>
          <div v-else-if="props.selectedNode" class="graph-node__empty">
            当前节点已被本地过滤隐藏。放宽标签、来源或聚焦条件后会恢复展示。
          </div>
          <div v-else class="graph-node__empty">
            选中一个节点后，这里会展示它的标签、所属论文、连接度和摘要信息。
          </div>
        </div>

        <div class="graph-catalog__inspector-card">
          <div class="graph-catalog__inspector-label">邻居预览</div>
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
          <div class="graph-catalog__inspector-label">热点实体 Top 8</div>
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

    <section v-if="paperGroups.length" class="graph-catalog__paper-board">
      <div class="graph-catalog__paper-head">
        <div>
          <div class="graph-catalog__canvas-title">论文图谱看板</div>
          <div class="graph-catalog__canvas-tip">
            适合比赛演示时快速说明每篇论文在图谱里的覆盖范围，包括方法、任务、数据集和指标的分布。
          </div>
        </div>
      </div>
      <div class="graph-catalog__paper-grid">
        <article
          v-for="paper in paperGroups"
          :key="paper.title"
          class="graph-paper"
        >
          <div class="graph-paper__title">{{ paper.title }}</div>
          <div class="graph-paper__meta">
            {{ paper.node_count }} 节点 · {{ paper.relation_count }} 关系 · {{ paper.source_count }} 来源
          </div>
          <div class="graph-paper__chips">
            <span
              v-for="[label, count] in sortGraphLabels(Object.keys(paper.labels || {})).map((label) => [label, paper.labels[label]])"
              :key="label"
              class="graph-catalog__chip"
            >
              {{ label }} · {{ count }}
            </span>
          </div>
        </article>
      </div>
    </section>
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
.graph-defense__tracks,
.graph-catalog__toolbar,
.graph-catalog__toolbar-actions,
.graph-catalog__filter-head,
.graph-catalog__canvas-head,
.graph-catalog__inspector-top,
.graph-catalog__paper-head {
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

.graph-defense {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.graph-defense__hero,
.graph-defense__card,
.graph-defense__track {
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  box-shadow: var(--shadow-card);
}

.graph-defense__eyebrow,
.graph-defense__card-label,
.graph-defense__track-head {
  font-size: 0.74rem;
  letter-spacing: 0.08em;
  color: var(--text-muted);
}

.graph-defense__headline {
  margin-top: 10px;
  font-size: 1.28rem;
  line-height: 1.5;
  color: var(--text-primary);
  font-weight: 700;
}

.graph-defense__subline {
  margin-top: 8px;
  max-width: 880px;
  font-size: 0.8rem;
  line-height: 1.8;
  color: var(--text-secondary);
}

.graph-defense__hero-meta {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.graph-defense__hero-chip {
  display: inline-flex;
  align-items: center;
  padding: 7px 12px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-secondary);
  font-size: 0.72rem;
}

.graph-defense__cards {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.graph-defense__card-value {
  margin-top: 10px;
  font-size: 0.96rem;
  line-height: 1.6;
  color: var(--text-primary);
  font-weight: 700;
}

.graph-defense__card-detail {
  margin-top: 8px;
  font-size: 0.74rem;
  line-height: 1.7;
  color: var(--text-secondary);
}

.graph-defense__tracks {
  align-items: stretch;
}

.graph-defense__tracks > * {
  flex: 1;
}

.graph-defense__track-body {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.graph-defense__track-body--questions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.graph-defense__point {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: 0.78rem;
  line-height: 1.8;
  color: var(--text-secondary);
}

.graph-defense__step {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-secondary);
  font-size: 0.78rem;
  line-height: 1.8;
}

.graph-defense__step-index {
  display: inline-flex;
  width: fit-content;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(127, 142, 255, 0.12);
  color: var(--text-primary);
  font-size: 0.7rem;
  letter-spacing: 0.04em;
}

.graph-defense__point-index {
  min-width: 22px;
  height: 22px;
  border-radius: 999px;
  border: 1px solid rgba(127, 142, 255, 0.24);
  background: rgba(127, 142, 255, 0.14);
  color: var(--text-primary);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.72rem;
  font-weight: 700;
}

.graph-defense__question {
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-primary);
  text-align: left;
  line-height: 1.7;
  cursor: pointer;
  transition: transform 0.2s ease, border-color 0.2s ease, background 0.2s ease;
}

.graph-defense__question:hover {
  transform: translateY(-1px);
  border-color: var(--border-strong);
  background: var(--bg-card-hover);
}

.graph-catalog__toolbar {
  align-items: end;
  flex-wrap: wrap;
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
.graph-catalog__source-panel,
.graph-catalog__overview-card,
.graph-catalog__meta-card,
.graph-catalog__canvas,
.graph-catalog__inspector-card,
.graph-paper {
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
  grid-template-columns: repeat(6, minmax(0, 1fr));
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

.graph-catalog__overview-card:nth-child(1) {
  background: linear-gradient(180deg, rgba(127, 142, 255, 0.12), rgba(255, 255, 255, 0.03));
}

.graph-catalog__overview-card:nth-child(2) {
  background: linear-gradient(180deg, rgba(104, 209, 174, 0.1), rgba(255, 255, 255, 0.03));
}

.graph-catalog__overview-card:nth-child(3) {
  background: linear-gradient(180deg, rgba(110, 184, 255, 0.1), rgba(255, 255, 255, 0.03));
}

.graph-catalog__filter-grid,
.graph-catalog__meta-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.graph-catalog__chips,
.graph-paper__chips {
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
  background: rgba(127, 142, 255, 0.14);
  color: var(--text-secondary);
  font-size: 0.72rem;
  line-height: 1;
  border: 1px solid transparent;
}

.graph-catalog__chip--filter {
  cursor: pointer;
  transition: transform 0.2s ease, border-color 0.2s ease, background 0.2s ease;
}

.graph-catalog__chip--filter:hover {
  transform: translateY(-1px);
  border-color: rgba(127, 142, 255, 0.24);
}

.graph-catalog__chip--relation {
  background: rgba(110, 184, 255, 0.12);
}

.graph-catalog__chip--source {
  background: rgba(104, 209, 174, 0.12);
}

.graph-catalog__chip--inactive {
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-muted);
}

.graph-catalog__chip--muted {
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-muted);
}

.graph-catalog__empty,
.graph-node__empty {
  padding: 18px;
  border-radius: 16px;
  border: 1px dashed var(--border-color);
  color: var(--text-muted);
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
  background: rgba(255, 255, 255, 0.03);
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
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  font-size: 0.76rem;
  color: var(--text-secondary);
  vertical-align: top;
}

.graph-catalog__table th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: rgba(18, 26, 46, 0.96);
  color: var(--text-muted);
}

.graph-catalog__table tbody tr {
  cursor: pointer;
  transition: background 0.2s ease;
}

.graph-catalog__table tbody tr:hover,
.graph-catalog__table-row--active {
  background: rgba(127, 142, 255, 0.08);
}

.graph-table__name,
.graph-node__title,
.graph-paper__title {
  font-size: 0.84rem;
  font-weight: 700;
  color: var(--text-primary);
}

.graph-table__desc,
.graph-node__meta,
.graph-node__desc,
.graph-paper__meta {
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
  background: rgba(255, 255, 255, 0.05);
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
  background: rgba(255, 255, 255, 0.04);
  text-align: left;
  cursor: pointer;
  transition: transform 0.2s ease, border-color 0.2s ease, background 0.2s ease;
}

.graph-neighbors__item:hover,
.graph-ranking__item:hover,
.graph-paper:hover {
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

.graph-catalog__paper-board {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.graph-catalog__paper-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

@media (max-width: 1280px) {
  .graph-defense__cards {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .graph-catalog__overview {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .graph-catalog__controls-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 1100px) {
  .graph-defense__track-body--questions,
  .graph-catalog__layout,
  .graph-catalog__filter-grid,
  .graph-catalog__meta-grid,
  .graph-catalog__paper-grid {
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
  .graph-defense__tracks,
  .graph-catalog__toolbar,
  .graph-catalog__toolbar-actions,
  .graph-catalog__filter-head,
  .graph-catalog__canvas-head,
  .graph-catalog__inspector-top,
  .graph-catalog__paper-head {
    align-items: stretch;
    flex-direction: column;
  }

  .graph-catalog__overview,
  .graph-defense__cards,
  .graph-catalog__controls-grid {
    grid-template-columns: 1fr;
  }

  .graph-catalog__chart {
    height: 440px;
  }
}
</style>

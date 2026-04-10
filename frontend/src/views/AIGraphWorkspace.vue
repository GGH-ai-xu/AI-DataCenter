<script setup>
import { computed, onMounted, proxyRefs, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import GraphCatalogViewer from '../components/ai/GraphCatalogViewer.vue'
import GraphCypherPreview from '../components/ai/GraphCypherPreview.vue'
import GraphExecuteResult from '../components/ai/GraphExecuteResult.vue'
import GraphImportPanel from '../components/ai/GraphImportPanel.vue'
import GraphQAPanel from '../components/ai/GraphQAPanel.vue'
import GraphStrategyGenerator from '../components/ai/GraphStrategyGenerator.vue'
import WorkspaceSummary from '../components/workspace/WorkspaceSummary.vue'
import WorkspaceTabs from '../components/workspace/WorkspaceTabs.vue'
import { useAiAssistantLlm } from '../composables/useAiAssistantLlm.js'
import { useGraphWorkspace } from '../composables/useGraphWorkspace.js'
import { graphStrategy } from '../services/api.js'

defineOptions({ name: 'AIGraphWorkspace' })

const router = useRouter()
const knowledgeTab = ref('import')
const graphWorkspace = proxyRefs(useGraphWorkspace())
const { llmReady, loadAssistantCapability } = useAiAssistantLlm()

const knowledgeTabs = Object.freeze([
  { key: 'import', label: '知识入图', desc: '工作台' },
  { key: 'catalog', label: '图谱展示', desc: '分析台' },
  { key: 'qa', label: '图谱问答', desc: '问答台' },
  { key: 'strategy', label: '策略生成', desc: '策略台' },
])

const graphStrategyForm = ref({
  message: '',
})
const graphStrategyBusy = ref(false)
const graphStrategyResult = ref(null)

const graphStatusLabel = computed(() => (
  graphWorkspace.summary.neo4j_connected ? '图库在线' : '图库离线'
))
const canGenerateGraphStrategy = computed(() => (
  Boolean(graphStrategyForm.value.message.trim())
  && Boolean(graphWorkspace.summary.neo4j_connected)
))

async function generateGraphStrategy() {
  const message = graphStrategyForm.value.message.trim()
  if (!message || graphStrategyBusy.value) return

  graphStrategyBusy.value = true
  try {
    const { data } = await graphStrategy({ message })
    graphStrategyResult.value = data
  } catch (error) {
    graphStrategyResult.value = {
      summary: error?.response?.data?.detail || '图谱策略生成失败。',
      strategy_steps: [],
      control_prompt: '',
      code_title: '未生成',
      code_language: 'python',
      code_snippet: '# 图谱策略生成失败，请检查 Neo4j 和当前图谱内容',
      risk_notice: '请先确认图谱已导入且 Neo4j 在线。',
      evidence: [],
      follow_ups: [],
      matched_node_count: 0,
      matched_relationship_count: 0,
      used_llm: false,
      focus: {},
      runtime_summary: '',
    }
  } finally {
    graphStrategyBusy.value = false
  }
}

function openGraphQa(question = '') {
  knowledgeTab.value = 'qa'
  const normalizedQuestion = String(question || '').trim()
  if (!normalizedQuestion) return
  graphWorkspace.qaForm.question = normalizedQuestion
  void graphWorkspace.askGraphQuestion(normalizedQuestion)
}

function sendGraphStrategyToWorkbench(prompt = '', autorun = false) {
  const draft = String(prompt || graphStrategyResult.value?.control_prompt || '').trim()
  if (!draft) return
  void router.push({
    path: '/ai/workbench',
    query: {
      draft,
      ...(autorun ? { autorun: '1' } : {}),
    },
  })
}

watch(knowledgeTab, (tab) => {
  if (
    tab === 'catalog'
    && graphWorkspace.summary.neo4j_connected
    && !graphWorkspace.graphView.nodes.length
  ) {
    void graphWorkspace.refreshGraphView({ silent: true })
  }
})

async function initializeGraphWorkspace() {
  await loadAssistantCapability()
  const nextSummary = await graphWorkspace.refreshSummary({ silent: true })
  if (nextSummary?.neo4j_connected) {
    await graphWorkspace.refreshGraphView({ silent: true })
  }
}

onMounted(() => {
  void initializeGraphWorkspace()
})
</script>

<template>
  <div class="ai-page ink-page-shell">
    <WorkspaceSummary title="图谱工作台" description="把入图、检索、问答和策略生成放到独立图谱域中处理。">
      <template #meta>
        <div class="ink-inline-meta">
          <span class="status-badge" :class="graphWorkspace.summary.neo4j_connected ? 'status-badge--ok' : 'status-badge--warning'">
            {{ graphStatusLabel }}
          </span>
          <span class="status-badge" :class="llmReady ? 'status-badge--ok' : 'status-badge--warning'">
            {{ llmReady ? 'LLM 已就绪' : 'LLM 未就绪' }}
          </span>
        </div>
      </template>
    </WorkspaceSummary>

    <div class="graph-workspace-shell">
      <div class="graph-workspace-shell__nav">
        <WorkspaceTabs
          v-model="knowledgeTab"
          :items="knowledgeTabs"
        />
      </div>

      <div v-if="knowledgeTab === 'import'" class="graph-workspace">
        <GraphImportPanel
          :form="graphWorkspace.form"
          :summary="graphWorkspace.summary"
          :draft-result="graphWorkspace.draftResult"
          :feedback="graphWorkspace.feedback"
          :llm-ready="llmReady"
          :refresh-busy="graphWorkspace.refreshBusy"
          :draft-busy="graphWorkspace.draftBusy"
          :execute-busy="graphWorkspace.executeBusy"
          :reconnect-busy="graphWorkspace.reconnectBusy"
          :demo-busy="graphWorkspace.demoBusy"
          :can-generate="graphWorkspace.canGenerate"
          :can-execute="graphWorkspace.canExecute"
          @generate="graphWorkspace.generateDraft"
          @execute="graphWorkspace.executeImport"
          @refresh="graphWorkspace.refreshSummary"
          @recover="graphWorkspace.recoverConnection"
          @reset="graphWorkspace.resetWorkspaceState"
          @demo="graphWorkspace.rebuildDemo"
        />

        <div class="graph-workspace__stack">
          <GraphCypherPreview :draft-result="graphWorkspace.draftResult" />
          <GraphExecuteResult
            :summary="graphWorkspace.summary"
            :mode="graphWorkspace.form.mode"
            :execution-result="graphWorkspace.executionResult"
          />
        </div>
      </div>

      <GraphCatalogViewer
        v-else-if="knowledgeTab === 'catalog'"
        :summary="graphWorkspace.summary"
        :graph-view="graphWorkspace.graphView"
        :filters="graphWorkspace.graphFilters"
        :selected-node="graphWorkspace.selectedGraphNode"
        :selected-node-id="graphWorkspace.selectedGraphNodeId"
        :view-busy="graphWorkspace.viewBusy"
        :expand-busy="graphWorkspace.expandBusy"
        :expanding-node-id="graphWorkspace.expandingNodeId"
        @refresh="graphWorkspace.refreshGraphView"
        @select="graphWorkspace.selectGraphNode"
        @expand="graphWorkspace.expandGraphNode"
        @ask="openGraphQa"
      />

      <GraphQAPanel
        v-else-if="knowledgeTab === 'qa'"
        :summary="graphWorkspace.summary"
        :form="graphWorkspace.qaForm"
        :result="graphWorkspace.qaResult"
        :busy="graphWorkspace.qaBusy"
        :can-ask="graphWorkspace.canAsk"
        @ask="graphWorkspace.askGraphQuestion"
      />

      <GraphStrategyGenerator
        v-else
        :summary="graphWorkspace.summary"
        :form="graphStrategyForm"
        :result="graphStrategyResult"
        :busy="graphStrategyBusy"
        :can-generate="canGenerateGraphStrategy"
        :llm-ready="llmReady"
        @generate="generateGraphStrategy"
        @use-control="sendGraphStrategyToWorkbench"
        @use-control-plan="sendGraphStrategyToWorkbench($event, true)"
        @ask="openGraphQa"
      />
    </div>
  </div>
</template>

<style scoped>
.ai-page {
  max-width: 1280px;
  margin: 0 auto;
}

.graph-workspace-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.graph-workspace-shell__nav {
  padding-bottom: 4px;
}

.graph-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1.08fr) minmax(0, 0.92fr);
  gap: 16px;
  align-items: start;
}

.graph-workspace__stack {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

@media (max-width: 1100px) {
  .graph-workspace {
    grid-template-columns: 1fr;
  }
}
</style>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import WorkspaceTabs from '../components/workspace/WorkspaceTabs.vue'

defineOptions({ name: 'AIWorkspaceLayout' })

const route = useRoute()
const router = useRouter()

const AI_WORKSPACE_TABS = Object.freeze([
  { key: 'workbench', label: '智能工作台', desc: '对话与执行' },
  { key: 'graph', label: '图谱工作台', desc: '入图与策略' },
])

const activeTab = computed(() => (
  route.name === 'AIGraphWorkspace' ? 'graph' : 'workbench'
))

function switchTab(nextTab) {
  const nextPath = nextTab === 'graph' ? '/ai/graph' : '/ai/workbench'
  if (route.path !== nextPath) {
    void router.push(nextPath)
  }
}
</script>

<template>
  <div class="ai-workspace-layout">
    <div class="workspace-nav-layout">
      <div class="workspace-nav-layout__nav">
        <WorkspaceTabs
          :model-value="activeTab"
          :items="AI_WORKSPACE_TABS"
          compact
          @update:model-value="switchTab"
        />
      </div>

      <section class="workspace-nav-layout__content">
        <router-view />
      </section>
    </div>
  </div>
</template>

<style scoped>
.ai-workspace-layout {
  max-width: 1280px;
  margin: 0 auto;
}
</style>

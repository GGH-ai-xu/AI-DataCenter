<script setup>
import { computed, proxyRefs } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import WorkspaceSummary from '../components/workspace/WorkspaceSummary.vue'
import WorkspaceTabs from '../components/workspace/WorkspaceTabs.vue'
import { buildGovernanceHeaderModel, buildGovernanceReviewModel, GOVERNANCE_TABS } from '../lib/governancePageModels.js'
import { useActionFeedback } from '../composables/useActionFeedback.js'
import { useExecutionMode } from '../composables/useExecutionMode.js'
import { useGovernanceData } from '../composables/useGovernanceData.js'
import { useAppStore } from '../stores/app.js'

const route = useRoute()
const router = useRouter()
const store = useAppStore()
const execution = proxyRefs(useExecutionMode())
const feedback = proxyRefs(useActionFeedback())

const activeSection = computed(() => {
  if (route.name === 'GovernancePolicies') return 'policies'
  if (route.name === 'GovernanceReview') return 'review'
  return 'actions'
})

const governance = proxyRefs(useGovernanceData({
  activeSection,
}))

const headerModel = computed(() => buildGovernanceHeaderModel(activeSection.value, {
  taskSummary: store.taskSummary,
  fairnessOverview: governance.actionsState?.fairness?.overview,
  scheduler: governance.policiesState?.scheduler,
  carbon: governance.policiesState?.carbon,
  auditLogs: governance.reviewState?.auditLogs,
  evaluation: governance.reviewState?.evaluation,
}))
const activeSummaryBadge = computed(() => headerModel.value.quickStats?.[0] || null)

const reviewModel = computed(() => buildGovernanceReviewModel({
  auditLogs: governance.reviewState?.auditLogs,
  evaluation: governance.reviewState?.evaluation,
}))

function switchSection(next) {
  router.push(`/governance/${next}`)
}
</script>

<template>
  <div class="governance-page ink-page-shell">
    <WorkspaceSummary :title="headerModel.title" :description="headerModel.description">
      <template #meta>
        <div class="ink-inline-meta">
          <span class="status-badge" :class="execution.modeBadgeClass">{{ execution.modeLabel }}</span>
          <span class="status-badge status-badge--ok">治理台</span>
          <span v-if="activeSummaryBadge" class="status-badge">
            {{ activeSummaryBadge.label }} {{ activeSummaryBadge.value }}
          </span>
        </div>
      </template>
    </WorkspaceSummary>

    <div class="workspace-nav-layout">
      <div class="workspace-nav-layout__nav">
        <WorkspaceTabs
          :model-value="activeSection"
          :items="GOVERNANCE_TABS"
          @update:model-value="switchSection"
        />
      </div>

      <section class="workspace-nav-layout__content">
        <div v-if="feedback.actionNotice" class="tech-card notice" :class="`notice--${feedback.actionNotice.tone}`">
          <div class="notice__title">{{ feedback.actionNotice.title }}</div>
          <div class="notice__detail">{{ feedback.actionNotice.detail }}</div>
        </div>

        <router-view v-slot="{ Component }">
          <component
            :is="Component"
            :execution="execution"
            :feedback="feedback"
            :governance="governance"
            :review-model="reviewModel"
          />
        </router-view>
      </section>
    </div>
  </div>
</template>

<style scoped>
.notice {
  padding: 14px 16px;
  margin-bottom: 14px;
}

.notice--ok {
  border-color: var(--state-ok-border);
  background: var(--state-ok-bg);
}

.notice--warning {
  border-color: var(--state-warning-border);
  background: var(--state-warning-bg);
}

.notice--critical {
  border-color: var(--state-danger-border);
  background: var(--state-danger-bg);
}

.notice__title {
  font-size: 0.82rem;
  font-weight: 700;
  color: var(--text-primary);
}

.notice__detail {
  margin-top: 6px;
  font-size: 0.78rem;
  color: var(--text-secondary);
  line-height: 1.7;
}
</style>

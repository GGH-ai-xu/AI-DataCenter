<script setup>
import PolicyActionDock from './PolicyActionDock.vue'
import PolicyAdvancedPanel from './PolicyAdvancedPanel.vue'
import PolicyBudgetConsole from './PolicyBudgetConsole.vue'

const props = defineProps({
  budgetTitle: { type: String, required: true },
  carbonTitle: { type: String, required: true },
  advancedTitle: { type: String, required: true },
  budget: { type: Object, required: true },
  budgetDraft: { type: Object, required: true },
  budgetCardState: { type: Object, required: true },
  carbonBudget: { type: Object, required: true },
  carbonDraft: { type: Object, required: true },
  carbonCardState: { type: Object, required: true },
  autoEnabled: { type: Boolean, required: true },
  executionBanner: { type: Object, required: true },
  executionReady: { type: Boolean, required: true },
  riskAcknowledged: { type: Boolean, required: true },
  scheduleResult: { type: Object, default: null },
  showAdvanced: { type: Boolean, required: true },
  rulesUsers: { type: Array, default: () => [] },
  gpuTargets: { type: Array, default: () => [] },
  powerInputs: { type: Object, required: true },
  userRulesComponent: { type: Object, required: true },
  formatActionLabel: { type: Function, required: true },
  formatActionTarget: { type: Function, required: true },
  handlers: { type: Object, required: true },
})

const emit = defineEmits(['toggle-advanced'])
</script>

<template>
  <div class="policies-console-layout">
    <div class="policies-console-layout__primary">
      <PolicyBudgetConsole
        :budget-title="props.budgetTitle"
        :carbon-title="props.carbonTitle"
        :budget="props.budget"
        :budget-draft="props.budgetDraft"
        :budget-card-state="props.budgetCardState"
        :carbon-budget="props.carbonBudget"
        :carbon-draft="props.carbonDraft"
        :carbon-card-state="props.carbonCardState"
        :format-action-label="props.formatActionLabel"
        :format-action-target="props.formatActionTarget"
        :handlers="props.handlers"
      />
    </div>

    <div class="policies-console-layout__side">
      <PolicyActionDock
        :advanced-title="props.advancedTitle"
        :auto-enabled="props.autoEnabled"
        :execution-banner="props.executionBanner"
        :execution-ready="props.executionReady"
        :risk-acknowledged="props.riskAcknowledged"
        :schedule-result="props.scheduleResult"
        :show-advanced="props.showAdvanced"
        :handlers="props.handlers"
        @toggle-advanced="emit('toggle-advanced')"
      />
    </div>

    <PolicyAdvancedPanel
      v-if="props.showAdvanced"
      :advanced-title="props.advancedTitle"
      :rules-users="props.rulesUsers"
      :gpu-targets="props.gpuTargets"
      :power-inputs="props.powerInputs"
      :execution-ready="props.executionReady"
      :user-rules-component="props.userRulesComponent"
      :handlers="props.handlers"
    />
  </div>
</template>

<style scoped>
.policies-console-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.28fr) minmax(320px, 0.9fr);
  gap: 16px;
  align-items: start;
}

.policies-console-layout__primary,
.policies-console-layout__side {
  min-width: 0;
}

.policy-advanced-panel {
  grid-column: 1 / -1;
}

@media (max-width: 1080px) {
  .policies-console-layout {
    grid-template-columns: 1fr;
  }
}
</style>

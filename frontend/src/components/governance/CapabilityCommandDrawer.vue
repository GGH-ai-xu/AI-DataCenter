<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  control: {
    type: Object,
    required: true,
  },
})

const argumentText = ref('{}')
const reason = ref('')
const acknowledgeRisk = ref(false)
const jsonError = ref('')

const drawerState = computed(() => props.control.drawer || {})
const drawerItems = computed(
  () => props.control.drawerModel?.items || drawerState.value.items || [],
)
const selectedCapability = computed(() => {
  const selectedName = drawerState.value.selectedName
  return (
    drawerItems.value.find((item) => item.name === selectedName)
    || drawerItems.value[0]
    || null
  )
})

watch(drawerItems, (items) => {
  if (!items.length) return
  if (!drawerState.value.selectedName) {
    drawerState.value.selectedName = items[0].name
  }
})

watch(selectedCapability, () => {
  argumentText.value = '{}'
  reason.value = ''
  acknowledgeRisk.value = false
  jsonError.value = ''
})

function selectCapability(item) {
  drawerState.value.selectedName = item.name
}

function closeDrawer() {
  props.control.closeDrawer?.()
}

function sourcePage(section) {
  if (section === 'cluster') return 'governance-cluster'
  if (section === 'policies') return 'governance-policies'
  if (section === 'review') return 'governance-review'
  return 'governance-actions'
}

async function submitCommand() {
  if (!selectedCapability.value) return
  jsonError.value = ''
  let parsedArguments = {}
  try {
    parsedArguments = JSON.parse(argumentText.value || '{}')
  } catch (error) {
    jsonError.value = error?.message || '参数 JSON 解析失败'
    return
  }
  await props.control.submitCommand?.({
    capability_name: selectedCapability.value.name,
    arguments: parsedArguments,
    acknowledge_risk: acknowledgeRisk.value,
    reason: reason.value,
    source_page: sourcePage(drawerState.value.section),
  })
}
</script>

<template>
  <teleport to="body">
    <div v-if="drawerState.open" class="capability-drawer">
      <button class="capability-drawer__backdrop" type="button" @click="closeDrawer" />
      <aside class="tech-card capability-drawer__panel">
        <header class="capability-drawer__header">
          <div>
            <div class="capability-drawer__eyebrow">高级能力</div>
            <h3>统一控制面</h3>
          </div>
          <button type="button" class="capability-drawer__close" @click="closeDrawer">
            关闭
          </button>
        </header>

        <div class="capability-drawer__body">
          <div class="capability-drawer__rail">
            <button
              v-for="item in drawerItems"
              :key="item.name"
              type="button"
              class="capability-drawer__item"
              :class="{ 'capability-drawer__item--active': item.name === selectedCapability?.name }"
              @click="selectCapability(item)"
            >
              <strong>{{ item.label }}</strong>
              <span>{{ item.domain }}</span>
            </button>
            <div v-if="!drawerItems.length" class="capability-drawer__empty">
              当前分区暂无可用高级能力。
            </div>
          </div>

          <div class="capability-drawer__detail">
            <template v-if="selectedCapability">
              <div class="capability-drawer__meta">
                <span class="status-badge">{{ selectedCapability.domain }}</span>
                <span class="status-badge">{{ selectedCapability.risk_level }}</span>
                <span class="status-badge">{{ selectedCapability.permission_mode }}</span>
              </div>
              <div class="capability-drawer__title">{{ selectedCapability.label }}</div>
              <div class="capability-drawer__desc">{{ selectedCapability.description || '暂无描述。' }}</div>

              <label class="capability-drawer__field">
                <span>参数 JSON</span>
                <textarea
                  v-model="argumentText"
                  rows="8"
                  spellcheck="false"
                />
              </label>

              <label class="capability-drawer__field">
                <span>操作说明</span>
                <input v-model="reason" type="text" placeholder="可选，记录本次人工操作原因" />
              </label>

              <label class="capability-drawer__check">
                <input v-model="acknowledgeRisk" type="checkbox" />
                <span>我已确认该能力可能直接触发真实执行</span>
              </label>

              <div v-if="jsonError || drawerState.error" class="capability-drawer__error">
                {{ jsonError || drawerState.error }}
              </div>

              <div class="capability-drawer__actions">
                <button
                  type="button"
                  class="btn-tech btn-tech--primary"
                  :disabled="drawerState.submitting"
                  @click="submitCommand"
                >
                  {{ drawerState.submitting ? '提交中...' : '执行能力' }}
                </button>
              </div>

              <div v-if="drawerState.latestCommand" class="capability-drawer__result">
                <div class="capability-drawer__result-title">最近一次结果</div>
                <div>命令 ID：{{ drawerState.latestCommand.command_id }}</div>
                <div>执行状态：{{ drawerState.latestCommand.execution_state }}</div>
                <div>审批状态：{{ drawerState.latestCommand.approval_state }}</div>
                <div>结果摘要：{{ drawerState.latestCommand.result_summary || '暂无' }}</div>
              </div>
            </template>
          </div>
        </div>
      </aside>
    </div>
  </teleport>
</template>

<style scoped>
.capability-drawer {
  position: fixed;
  inset: 0;
  z-index: 70;
}

.capability-drawer__backdrop {
  position: absolute;
  inset: 0;
  border: none;
  background: rgba(8, 12, 20, 0.48);
}

.capability-drawer__panel {
  position: absolute;
  top: 20px;
  right: 20px;
  bottom: 20px;
  width: min(900px, calc(100vw - 40px));
  padding: 20px;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 16px;
  overflow: hidden;
}

.capability-drawer__header,
.capability-drawer__actions,
.capability-drawer__meta {
  display: flex;
  align-items: center;
  gap: 10px;
}

.capability-drawer__header {
  justify-content: space-between;
}

.capability-drawer__eyebrow {
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.capability-drawer__close,
.capability-drawer__item {
  border: 1px solid var(--border-color);
  background: var(--bg-surface);
  color: var(--text-primary);
}

.capability-drawer__close {
  min-height: 38px;
  padding: 0 14px;
  border-radius: 12px;
}

.capability-drawer__body {
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(220px, 260px) minmax(0, 1fr);
  gap: 16px;
}

.capability-drawer__rail,
.capability-drawer__detail {
  min-height: 0;
  overflow: auto;
}

.capability-drawer__rail {
  display: grid;
  align-content: start;
  gap: 10px;
}

.capability-drawer__item {
  display: grid;
  gap: 4px;
  padding: 12px 14px;
  border-radius: 14px;
  text-align: left;
}

.capability-drawer__item strong {
  font-size: 0.86rem;
}

.capability-drawer__item span,
.capability-drawer__desc,
.capability-drawer__empty,
.capability-drawer__result {
  font-size: 0.78rem;
  line-height: 1.7;
  color: var(--text-secondary);
}

.capability-drawer__item--active {
  border-color: var(--state-ok-border);
  background: var(--state-ok-bg);
}

.capability-drawer__detail {
  display: grid;
  align-content: start;
  gap: 14px;
}

.capability-drawer__title {
  font-size: 1rem;
  font-weight: 700;
  color: var(--text-primary);
}

.capability-drawer__field {
  display: grid;
  gap: 6px;
  color: var(--text-secondary);
  font-size: 0.78rem;
}

.capability-drawer__field textarea,
.capability-drawer__field input {
  width: 100%;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid var(--field-border);
  background: var(--field-background);
  color: var(--text-primary);
}

.capability-drawer__check {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  color: var(--text-secondary);
  font-size: 0.78rem;
}

.capability-drawer__error {
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid var(--state-danger-border);
  background: var(--state-danger-bg);
  color: var(--state-danger-text);
  font-size: 0.78rem;
}

.capability-drawer__result {
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: var(--bg-surface);
}

.capability-drawer__result-title {
  margin-bottom: 6px;
  font-weight: 700;
  color: var(--text-primary);
}

@media (max-width: 960px) {
  .capability-drawer__panel {
    top: 12px;
    right: 12px;
    bottom: 12px;
    left: 12px;
    width: auto;
  }

  .capability-drawer__body {
    grid-template-columns: 1fr;
  }
}
</style>

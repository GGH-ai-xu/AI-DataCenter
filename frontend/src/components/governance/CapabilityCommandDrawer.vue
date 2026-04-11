<script setup>
import { computed, ref, watch } from 'vue'

import {
  buildCapabilityFormArguments,
  buildCapabilityFormDraft,
} from '../../lib/controlCapabilityModels.js'

const props = defineProps({
  control: {
    type: Object,
    required: true,
  },
})

const rawArgumentText = ref('{}')
const reason = ref('')
const acknowledgeRisk = ref(false)
const formDraft = ref({})

const drawerState = computed(() => props.control.drawer || {})
const drawerItems = computed(() => props.control.drawerModel?.items || drawerState.value.items || [])
const selectedCapability = computed(() => {
  const selectedName = drawerState.value.selectedName
  return drawerItems.value.find((item) => item.name === selectedName) || drawerItems.value[0] || null
})
const selectedFormDefinition = computed(() => selectedCapability.value?.formDefinition || null)
const usesTypedForm = computed(() => Boolean(selectedFormDefinition.value))
const previewState = computed(() => {
  if (!selectedCapability.value) return { payload: {}, text: '{}', error: '' }
  try {
    const payload = usesTypedForm.value
      ? buildCapabilityFormArguments(selectedCapability.value.name, formDraft.value)
      : JSON.parse(rawArgumentText.value || '{}')
    return {
      payload,
      text: JSON.stringify(payload, null, 2),
      error: '',
    }
  } catch (error) {
    return {
      payload: null,
      text: '',
      error: error?.message || '参数解析失败',
    }
  }
})

watch(drawerItems, (items) => {
  if (items.length && !drawerState.value.selectedName) {
    drawerState.value.selectedName = items[0].name
  }
})

watch(selectedCapability, (item) => {
  reason.value = ''
  acknowledgeRisk.value = false
  rawArgumentText.value = '{}'
  formDraft.value = item ? buildCapabilityFormDraft(item.name) : {}
}, { immediate: true })

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

function updateField(key, value) {
  formDraft.value = {
    ...formDraft.value,
    [key]: value,
  }
}

async function submitCommand() {
  if (!selectedCapability.value) return
  if (previewState.value.error || !previewState.value.payload) return
  await props.control.submitCommand?.({
    capability_name: selectedCapability.value.name,
    arguments: previewState.value.payload,
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
          <button type="button" class="capability-drawer__close" @click="closeDrawer">关闭</button>
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
            <div v-if="!drawerItems.length" class="capability-drawer__empty">当前分区暂无可用高级能力。</div>
          </div>

          <div v-if="selectedCapability" class="capability-drawer__detail">
            <div class="capability-drawer__meta">
              <span class="status-badge">{{ selectedCapability.domain }}</span>
              <span class="status-badge">{{ selectedCapability.risk_level }}</span>
              <span class="status-badge">{{ selectedCapability.permission_mode }}</span>
            </div>
            <div class="capability-drawer__title">{{ selectedCapability.label }}</div>
            <div class="capability-drawer__desc">{{ selectedCapability.description || '暂无描述。' }}</div>

            <section class="capability-drawer__card">
              <div class="capability-drawer__section-title">结构化参数</div>
              <template v-if="usesTypedForm">
                <div v-if="!selectedFormDefinition.fields.length" class="capability-drawer__hint">
                  当前能力无需填写结构化参数。
                </div>
                <div v-else class="capability-drawer__fields">
                  <label
                    v-for="field in selectedFormDefinition.fields"
                    :key="field.key"
                    class="capability-drawer__field"
                  >
                    <span>{{ field.label }}</span>
                    <textarea
                      v-if="field.type === 'textarea'"
                      :value="formDraft[field.key]"
                      rows="3"
                      @input="updateField(field.key, $event.target.value)"
                    />
                    <select
                      v-else-if="field.type === 'select'"
                      :value="formDraft[field.key]"
                      @change="updateField(field.key, $event.target.value)"
                    >
                      <option v-for="option in field.options || []" :key="option.value" :value="option.value">
                        {{ option.label }}
                      </option>
                    </select>
                    <label v-else-if="field.type === 'toggle'" class="capability-drawer__toggle">
                      <input
                        type="checkbox"
                        :checked="Boolean(formDraft[field.key])"
                        @change="updateField(field.key, $event.target.checked)"
                      />
                      <span>{{ Boolean(formDraft[field.key]) ? '开启' : '关闭' }}</span>
                    </label>
                    <input
                      v-else
                      :value="formDraft[field.key]"
                      :type="field.type === 'number' ? 'number' : 'text'"
                      :placeholder="field.placeholder || ''"
                      @input="updateField(field.key, $event.target.value)"
                    />
                  </label>
                </div>
              </template>
              <template v-else>
                <div class="capability-drawer__hint">当前能力未定义结构化表单，请使用 JSON 参数。</div>
                <label class="capability-drawer__field">
                  <span>参数 JSON</span>
                  <textarea
                    v-model="rawArgumentText"
                    rows="8"
                    spellcheck="false"
                  />
                </label>
              </template>
            </section>

            <section class="capability-drawer__card">
              <div class="capability-drawer__section-title">参数预览</div>
              <div v-if="previewState.error" class="capability-drawer__error">{{ previewState.error }}</div>
              <pre v-else class="capability-drawer__preview">{{ previewState.text }}</pre>
            </section>

            <label class="capability-drawer__field">
              <span>操作说明</span>
              <input v-model="reason" type="text" placeholder="可选，记录本次人工操作原因" />
            </label>

            <label class="capability-drawer__check">
              <input v-model="acknowledgeRisk" type="checkbox" />
              <span>我已确认该能力可能直接触发真实执行</span>
            </label>

            <div v-if="drawerState.error" class="capability-drawer__error">{{ drawerState.error }}</div>

            <div class="capability-drawer__actions">
              <button
                type="button"
                class="btn-tech btn-tech--primary"
                :disabled="drawerState.submitting || Boolean(previewState.error)"
                @click="submitCommand"
              >
                {{ drawerState.submitting ? '提交中...' : '执行能力' }}
              </button>
            </div>

            <div v-if="drawerState.latestCommand" class="capability-drawer__result">
              <div class="capability-drawer__section-title">最近一次结果</div>
              <div>命令 ID：{{ drawerState.latestCommand.command_id }}</div>
              <div>执行状态：{{ drawerState.latestCommand.execution_state }}</div>
              <div>审批状态：{{ drawerState.latestCommand.approval_state }}</div>
              <div>结果摘要：{{ drawerState.latestCommand.result_summary || '暂无' }}</div>
            </div>
          </div>
        </div>
      </aside>
    </div>
  </teleport>
</template>

<style scoped>
.capability-drawer { position: fixed; inset: 0; z-index: 70; }
.capability-drawer__backdrop { position: absolute; inset: 0; border: none; background: rgba(8, 12, 20, 0.48); }
.capability-drawer__panel {
  position: absolute; top: 20px; right: 20px; bottom: 20px; width: min(920px, calc(100vw - 40px));
  padding: 20px; display: grid; grid-template-rows: auto minmax(0, 1fr); gap: 16px; overflow: hidden;
}
.capability-drawer__header, .capability-drawer__actions, .capability-drawer__meta { display: flex; gap: 10px; align-items: center; }
.capability-drawer__header { justify-content: space-between; }
.capability-drawer__body { min-height: 0; display: grid; grid-template-columns: 240px minmax(0, 1fr); gap: 16px; }
.capability-drawer__rail, .capability-drawer__detail { min-height: 0; overflow: auto; }
.capability-drawer__rail, .capability-drawer__detail, .capability-drawer__fields { display: grid; gap: 10px; align-content: start; }
.capability-drawer__close, .capability-drawer__item, .capability-drawer__field input, .capability-drawer__field textarea, .capability-drawer__field select {
  border: 1px solid var(--border-color); background: var(--bg-surface); color: var(--text-primary);
}
.capability-drawer__close, .capability-drawer__item, .capability-drawer__card { border-radius: 14px; }
.capability-drawer__close { min-height: 38px; padding: 0 14px; }
.capability-drawer__item { padding: 12px 14px; text-align: left; display: grid; gap: 4px; }
.capability-drawer__item--active { border-color: var(--state-ok-border); background: var(--state-ok-bg); }
.capability-drawer__eyebrow, .capability-drawer__field, .capability-drawer__hint, .capability-drawer__desc, .capability-drawer__empty, .capability-drawer__result {
  font-size: 0.78rem; line-height: 1.7; color: var(--text-secondary);
}
.capability-drawer__eyebrow { letter-spacing: 0.08em; text-transform: uppercase; color: var(--text-muted); }
.capability-drawer__title, .capability-drawer__section-title { font-weight: 700; color: var(--text-primary); }
.capability-drawer__title { font-size: 1rem; }
.capability-drawer__section-title { font-size: 0.82rem; }
.capability-drawer__card { padding: 14px; border: 1px solid var(--border-color); background: var(--bg-surface); display: grid; gap: 12px; }
.capability-drawer__field { display: grid; gap: 6px; }
.capability-drawer__field input, .capability-drawer__field textarea, .capability-drawer__field select { width: 100%; padding: 10px 12px; border-radius: 12px; }
.capability-drawer__toggle, .capability-drawer__check { display: flex; gap: 10px; align-items: center; }
.capability-drawer__preview, .capability-drawer__error {
  margin: 0; padding: 12px 14px; border-radius: 12px; font-size: 0.76rem; overflow: auto;
}
.capability-drawer__preview { background: rgba(9, 14, 22, 0.72); border: 1px solid var(--border-color); color: var(--text-secondary); }
.capability-drawer__error { border: 1px solid var(--state-danger-border); background: var(--state-danger-bg); color: var(--state-danger-text); }
.capability-drawer__result { padding: 14px; border: 1px solid var(--border-color); border-radius: 14px; background: var(--bg-surface); display: grid; gap: 4px; }

@media (max-width: 960px) {
  .capability-drawer__panel { inset: 12px; width: auto; }
  .capability-drawer__body { grid-template-columns: 1fr; }
}
</style>

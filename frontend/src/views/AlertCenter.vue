<script setup>
/**
 * AlertCenter.vue - 告警中心
 * 展示历史告警列表，支持确认告警
 */
import { computed, ref, onMounted } from 'vue'
import { getAlerts, acknowledgeAlert } from '../services/api'
import AlertHistoryTable from '../components/alerts/AlertHistoryTable.vue'
import { useAppStore } from '../stores/app'
import AlertSummaryPanel from '../components/alerts/AlertSummaryPanel.vue'
import WorkspacePaneLayout from '../components/workspace/WorkspacePaneLayout.vue'
import WorkspaceSummary from '../components/workspace/WorkspaceSummary.vue'

const store = useAppStore()
const historyAlerts = ref([])
const loading = ref(false)
const showUnackOnly = ref(false)

async function loadAlerts() {
  loading.value = true
  try {
    const { data } = await getAlerts(100, showUnackOnly.value)
    historyAlerts.value = data.alerts || []
  } catch (e) {
    historyAlerts.value = []
  }
  loading.value = false
}

async function ackAlert(id) {
  try {
    await acknowledgeAlert(id)
    store.$patch({
      alerts: store.alerts.map((alert) => (
        alert.id === id
          ? { ...alert, acknowledged: true }
          : alert
      )),
    })
    await loadAlerts()
  } catch (e) {}
}

const fmtTime = (ts) => new Date(ts * 1000).toLocaleString('zh-CN')
const formatAlertType = (value = '') => ({
  temperature: '温度',
  power: '功率',
  memory: '显存',
  self_check: '平台自检',
}[value] || value || '未知')

const severityConfig = {
  critical: { bg: 'rgba(196,30,58,0.08)', border: 'rgba(196,30,58,0.2)', color: '#C41E3A', icon: '⚠', label: '严重' },
  warning: { bg: 'rgba(184,134,11,0.08)', border: 'rgba(184,134,11,0.2)', color: '#B8860B', icon: '△', label: '警告' },
}

const pendingCount = computed(() => historyAlerts.value.filter(alert => !alert.acknowledged).length)
const criticalCount = computed(() => historyAlerts.value.filter(alert => alert.severity === 'critical').length)
const realtimeAlerts = computed(() => store.alerts.filter((alert) => !alert.acknowledged).slice(0, 5))

onMounted(loadAlerts)
</script>

<template>
  <div class="alert-page ink-page-shell">
    <WorkspaceSummary
      title="告警中心"
    >
      <template #meta>
        <div class="ink-inline-meta">
          <span class="status-badge status-badge--critical">{{ criticalCount }} 条严重</span>
          <span class="status-badge status-badge--warning">{{ pendingCount }} 条未确认</span>
          <span class="status-badge status-badge--ok">{{ realtimeAlerts.length }} 条实时</span>
        </div>
      </template>
    </WorkspaceSummary>

    <div class="workspace-summary-strip">
      <AlertSummaryPanel
        :critical-count="criticalCount"
        :pending-count="pendingCount"
        :realtime-count="realtimeAlerts.length"
      />
    </div>

    <WorkspacePaneLayout>
      <template #main>
        <section class="tech-card alert-table-panel">
          <div class="alert-toolbar">
            <div>
              <div class="section-title" style="font-size: 1rem">告警簿</div>
              <div class="alert-toolbar__hint">历史记录独立占据主内容区，避免顶部说明和实时流挤压表格宽度。</div>
            </div>
            <div class="alert-toolbar__actions">
              <label class="alert-toolbar__toggle">
                <input type="checkbox" v-model="showUnackOnly" @change="loadAlerts" />
                仅显示未确认
              </label>
              <button class="btn-tech" @click="loadAlerts" :disabled="loading">刷新</button>
            </div>
          </div>

          <AlertHistoryTable
            :alerts="historyAlerts"
            :loading="loading"
            :severity-config="severityConfig"
            :fmt-time="fmtTime"
            :format-alert-type="formatAlertType"
            @ack="ackAlert"
          />
        </section>
      </template>

      <template #side>
        <section class="tech-card alert-side-card">
          <div class="section-title" style="font-size: 1rem">实时告警</div>
          <div class="alert-side-card__hint">把最新风险集中在右侧稳定槽位，避免主表上下跳动。</div>
          <div v-if="realtimeAlerts.length" class="alert-stream">
            <div
              v-for="(alert, i) in realtimeAlerts"
              :key="i"
              class="alert-card"
              :style="{ background: severityConfig[alert.severity]?.bg, borderColor: severityConfig[alert.severity]?.border }"
            >
              <span class="alert-icon" :style="{ color: severityConfig[alert.severity]?.color }">{{ severityConfig[alert.severity]?.icon }}</span>
              <div style="flex: 1">
                <div style="font-size: 0.8125rem">{{ alert.message }}</div>
                <div style="font-size: 0.6875rem; color: var(--text-muted); margin-top: 2px">GPU {{ alert.gpu_index }} · {{ fmtTime(alert.timestamp) }}</div>
              </div>
            </div>
          </div>
          <div v-else class="alert-side-card__empty">当前没有未确认的实时告警。</div>
        </section>
      </template>
    </WorkspacePaneLayout>
  </div>
</template>

<style scoped>
.alert-page { max-width: 1460px; margin: 0 auto; }

.alert-table-panel,
.alert-side-card {
  padding: 18px 20px;
}

.alert-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.alert-toolbar__actions,
.alert-toolbar__toggle {
  display: flex;
  align-items: center;
  gap: 8px;
}

.alert-toolbar__toggle {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  cursor: pointer;
}

.alert-toolbar__toggle input {
  accent-color: var(--accent-primary);
}

.alert-toolbar__hint,
.alert-side-card__hint,
.alert-side-card__empty {
  font-size: 0.75rem;
  color: var(--text-muted);
  line-height: 1.7;
}

.alert-stream { display: flex; flex-direction: column; gap: 6px; }

.alert-card {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 16px; border-radius: 8px;
  border: 1px solid; font-size: 0.8125rem;
}

.alert-icon { font-size: 1.125rem; }

@media (max-width: 820px) {
  .alert-toolbar {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>

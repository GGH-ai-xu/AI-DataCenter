<script setup>
/**
 * AlertCenter.vue - 告警中心
 * 重构为时间工作台：实时流 / 今日告警簿 / 历史归档
 */
import { computed, onMounted, ref } from 'vue'
import { getAlerts, acknowledgeAlert } from '../services/api'
import { useAppStore } from '../stores/app'
import AlertSummaryPanel from '../components/alerts/AlertSummaryPanel.vue'
import WorkspaceSummary from '../components/workspace/WorkspaceSummary.vue'
import WorkspaceTabs from '../components/workspace/WorkspaceTabs.vue'
import AlertRealtimeStream from '../components/alerts/AlertRealtimeStream.vue'
import AlertDaybookTimeline from '../components/alerts/AlertDaybookTimeline.vue'
import AlertArchiveBoard from '../components/alerts/AlertArchiveBoard.vue'
import {
  ALERT_ARCHIVE_TYPES,
  ALERT_CENTER_TABS,
  buildAlertSummaryItems,
  buildArchiveGroups,
  buildRealtimeBuckets,
  buildTodayTimeline,
} from '../lib/alertCenterTransforms.js'

const ALERT_HISTORY_LIMIT = 200
const store = useAppStore()
const activeTab = ref('realtime')
const realtimeType = ref('all')
const archiveType = ref('temperature')
const historyAlerts = ref([])
const loading = ref(false)

async function loadAlerts() {
  loading.value = true
  try {
    const { data } = await getAlerts(ALERT_HISTORY_LIMIT, false)
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
  critical: { bg: 'rgba(239, 68, 68, 0.1)', border: 'rgba(239, 68, 68, 0.18)', color: '#EF4444', icon: '⚠', label: '严重' },
  warning: { bg: 'rgba(245, 158, 11, 0.1)', border: 'rgba(245, 158, 11, 0.18)', color: '#F59E0B', icon: '△', label: '警告' },
}

const realtimeAlerts = computed(() => (
  store.alerts.filter((alert) => !alert.acknowledged)
))
const summaryItems = computed(() => (
  buildAlertSummaryItems(historyAlerts.value, realtimeAlerts.value)
))
const realtimeBuckets = computed(() => (
  buildRealtimeBuckets(realtimeAlerts.value, realtimeType.value)
))
const todaySections = computed(() => (
  buildTodayTimeline(historyAlerts.value)
))
const archiveGroups = computed(() => (
  buildArchiveGroups(historyAlerts.value)
))
const realtimeFilterItems = computed(() => ([
  { key: 'all', label: '全部未确认' },
  ...ALERT_ARCHIVE_TYPES.map((item) => ({ key: item.key, label: item.label })),
]))

onMounted(loadAlerts)
</script>

<template>
  <div class="alert-page ink-page-shell">
    <WorkspaceSummary
      title="告警中心"
    >
      <template #meta>
        <div class="ink-inline-meta">
          <span class="status-badge status-badge--critical">{{ summaryItems[0]?.value || 0 }} 条严重</span>
          <span class="status-badge status-badge--warning">{{ summaryItems[1]?.value || 0 }} 条未确认</span>
          <span class="status-badge status-badge--ok">{{ summaryItems[2]?.value || 0 }} 条新增</span>
        </div>
      </template>
    </WorkspaceSummary>

    <div class="workspace-summary-strip">
      <AlertSummaryPanel :items="summaryItems" />
    </div>

    <div class="workspace-nav-layout">
      <div class="workspace-nav-layout__nav">
        <WorkspaceTabs v-model="activeTab" :items="ALERT_CENTER_TABS" />
      </div>

      <section class="workspace-nav-layout__content">
        <AlertRealtimeStream
          v-if="activeTab === 'realtime'"
          :buckets="realtimeBuckets"
          :loading="loading"
          :selected-type="realtimeType"
          :filter-items="realtimeFilterItems"
          :summary-items="summaryItems"
          :severity-config="severityConfig"
          :format-alert-type="formatAlertType"
          :fmt-time="fmtTime"
          @ack="ackAlert"
          @update:selectedType="realtimeType = $event"
        />
        <AlertDaybookTimeline
          v-else-if="activeTab === 'today'"
          :sections="todaySections"
          :loading="loading"
          :severity-config="severityConfig"
          :format-alert-type="formatAlertType"
          :fmt-time="fmtTime"
          @ack="ackAlert"
        />
        <AlertArchiveBoard
          v-else
          :type-key="archiveType"
          :groups="archiveGroups"
          :loading="loading"
          :severity-config="severityConfig"
          :format-alert-type="formatAlertType"
          :fmt-time="fmtTime"
          @ack="ackAlert"
          @update:typeKey="archiveType = $event"
        />
      </section>
    </div>
  </div>
</template>

<style scoped>
.alert-page {
  max-width: 1460px;
  margin: 0 auto;
}
</style>

<script setup>
/**
 * AlertCenter.vue - 告警中心
 * 展示历史告警列表，支持确认告警
 */
import { computed, ref, onMounted } from 'vue'
import { getAlerts, acknowledgeAlert } from '../services/api'
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
      eyebrow="实时告警 · 历史风险 · 分级确认"
      title="先看风险数量，再处理告警明细"
      description="把风险摘要、实时波动和历史台账拆成稳定层次，避免说明区与主表互相挤压。"
    >
      <template #meta>
        <div class="ink-inline-meta">
          <span class="status-badge status-badge--critical">{{ criticalCount }} 条严重</span>
          <span class="status-badge status-badge--warning">{{ pendingCount }} 条未确认</span>
          <span class="status-badge status-badge--ok">{{ realtimeAlerts.length }} 条实时</span>
        </div>
      </template>
      <AlertSummaryPanel
        :critical-count="criticalCount"
        :pending-count="pendingCount"
        :realtime-count="realtimeAlerts.length"
      />
    </WorkspaceSummary>

    <WorkspacePaneLayout>
      <template #main>
        <section class="tech-card alert-table-panel">
          <div class="alert-toolbar">
            <div>
              <div class="section-title" style="font-size: 1rem">告警簿</div>
              <div class="alert-toolbar__hint">历史记录独立占据主内容区，避免顶部说明和实时流挤压表格宽度。</div>
            </div>
            <div style="display: flex; gap: 8px; align-items: center">
              <label style="display: flex; align-items: center; gap: 6px; font-size: 0.8125rem; color: var(--text-secondary); cursor: pointer">
                <input type="checkbox" v-model="showUnackOnly" @change="loadAlerts" style="accent-color: var(--accent-primary)" />
                仅显示未确认
              </label>
              <button class="btn-tech" @click="loadAlerts" :disabled="loading">刷新</button>
            </div>
          </div>

          <div class="alert-table-wrap panel-scroll">
            <table class="alert-table">
              <thead>
                <tr>
                  <th>级别</th>
                  <th>GPU</th>
                  <th>类型</th>
                  <th>告警内容</th>
                  <th>数值</th>
                  <th>阈值</th>
                  <th>时间</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="alert in historyAlerts" :key="alert.id">
                  <td>
                    <span class="status-badge" :class="alert.severity === 'critical' ? 'status-badge--critical' : 'status-badge--warning'">
                      {{ severityConfig[alert.severity]?.label }}
                    </span>
                  </td>
                  <td><span class="gpu-tag">GPU {{ alert.gpu_index }}</span></td>
                  <td style="color: var(--text-secondary)">{{ formatAlertType(alert.alert_type) }}</td>
                  <td style="max-width: 300px">{{ alert.message }}</td>
                  <td class="stat-value" :style="{ color: severityConfig[alert.severity]?.color }">{{ alert.value?.toFixed(1) }}</td>
                  <td class="stat-value" style="color: var(--text-muted)">{{ alert.threshold }}</td>
                  <td style="font-size: 0.75rem; color: var(--text-muted); white-space: nowrap">{{ fmtTime(alert.timestamp) }}</td>
                  <td>
                    <button v-if="!alert.acknowledged" class="btn-tech" style="padding: 2px 8px; font-size: 0.6875rem" @click="ackAlert(alert.id)">确认</button>
                    <span v-else style="color: var(--text-muted); font-size: 0.75rem">已确认</span>
                  </td>
                </tr>
                <tr v-if="!historyAlerts.length && !loading">
                  <td colspan="8" style="text-align: center; color: var(--text-muted); padding: 40px">暂无告警记录</td>
                </tr>
              </tbody>
            </table>
          </div>
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

.alert-table-wrap {
  overflow-x: auto;
}

.alert-table { width: 100%; border-collapse: collapse; }
.alert-table th {
  text-align: left; padding: 12px 16px; font-size: 0.75rem; font-weight: 600;
  color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em;
  border-bottom: 1px solid var(--border-color);
}
.alert-table td {
  padding: 10px 16px; font-size: 0.8125rem;
  border-bottom: 1px solid rgba(255,255,255,0.03);
}
.alert-table tr:hover td { background: rgba(58,95,75,0.03); }

.gpu-tag { font-size: 0.6875rem; font-weight: 600; color: var(--accent-primary); background: rgba(58,95,75,0.1); padding: 2px 8px; border-radius: 4px; }

@media (max-width: 820px) {
  .alert-toolbar {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>

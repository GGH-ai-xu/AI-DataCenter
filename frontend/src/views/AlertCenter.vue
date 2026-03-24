<script setup>
/**
 * AlertCenter.vue - 告警中心
 * 展示历史告警列表，支持确认告警
 */
import { ref, onMounted } from 'vue'
import { getAlerts, acknowledgeAlert } from '../services/api'
import { useAppStore } from '../stores/app'

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
    await loadAlerts()
  } catch (e) {}
}

const fmtTime = (ts) => new Date(ts * 1000).toLocaleString('zh-CN')

const severityConfig = {
  critical: { bg: 'rgba(248,113,113,0.08)', border: 'rgba(248,113,113,0.2)', color: '#f87171', icon: '⚠', label: '严重' },
  warning: { bg: 'rgba(251,191,36,0.08)', border: 'rgba(251,191,36,0.2)', color: '#fbbf24', icon: '△', label: '警告' },
}

onMounted(loadAlerts)
</script>

<template>
  <div class="alert-page">
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px">
      <div class="section-title" style="font-size: 1rem">告警中心</div>
      <div style="display: flex; gap: 8px; align-items: center">
        <label style="display: flex; align-items: center; gap: 6px; font-size: 0.8125rem; color: var(--text-secondary); cursor: pointer">
          <input type="checkbox" v-model="showUnackOnly" @change="loadAlerts" style="accent-color: var(--accent-primary)" />
          仅显示未确认
        </label>
        <button class="btn-tech" @click="loadAlerts" :disabled="loading">刷新</button>
      </div>
    </div>

    <!-- 实时告警（WebSocket推送） -->
    <div v-if="store.alerts.length" style="margin-bottom: 20px">
      <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.05em">实时告警</div>
      <div class="alert-stream">
        <div
          v-for="(alert, i) in store.alerts.slice(0, 5)"
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
    </div>

    <!-- 历史告警列表 -->
    <div class="tech-card" style="padding: 0">
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
            <td style="color: var(--text-secondary)">{{ alert.alert_type }}</td>
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
  </div>
</template>

<style scoped>
.alert-page { max-width: 1400px; margin: 0 auto; }

.alert-stream { display: flex; flex-direction: column; gap: 6px; }

.alert-card {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 16px; border-radius: 8px;
  border: 1px solid; font-size: 0.8125rem;
}

.alert-icon { font-size: 1.125rem; }

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
.alert-table tr:hover td { background: rgba(56,189,248,0.03); }

.gpu-tag { font-size: 0.6875rem; font-weight: 600; color: var(--accent-primary); background: rgba(56,189,248,0.1); padding: 2px 8px; border-radius: 4px; }
</style>

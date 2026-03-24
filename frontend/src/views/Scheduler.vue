<script setup>
/**
 * Scheduler.vue - 智能调度页
 * 手动/自动调度控制、功耗限制设置、AI调度策略、能耗报告
 */
import { ref, onMounted } from 'vue'
import { useAppStore } from '../stores/app'
import { getSchedulerStatus, toggleAutoSchedule, setManualPowerLimit, runScheduleOnce, getScheduleReport } from '../services/api'

const store = useAppStore()
const autoEnabled = ref(false)
const timePeriod = ref('')
const powerInputs = ref({})
const scheduleResult = ref(null)
const report = ref('')
const reportLoading = ref(false)
const scheduleLoading = ref(false)

async function loadStatus() {
  try {
    const { data } = await getSchedulerStatus()
    autoEnabled.value = data.auto_enabled
    timePeriod.value = data.time_period_label
  } catch (e) {}
}

async function toggleAuto() {
  const next = !autoEnabled.value
  try {
    await toggleAutoSchedule(next)
    autoEnabled.value = next
  } catch (e) {}
}

async function setPower(gpuIndex) {
  const val = parseInt(powerInputs.value[gpuIndex])
  if (!val || val < 100 || val > 350) return
  try {
    await setManualPowerLimit(gpuIndex, val)
  } catch (e) {}
}

async function runOnce() {
  scheduleLoading.value = true
  try {
    const { data } = await runScheduleOnce()
    scheduleResult.value = data
  } catch (e) {
    scheduleResult.value = { error: '调度执行失败' }
  }
  scheduleLoading.value = false
}

async function loadReport() {
  reportLoading.value = true
  try {
    const { data } = await getScheduleReport()
    report.value = data.report
  } catch (e) {
    report.value = '报告生成失败'
  }
  reportLoading.value = false
}

onMounted(loadStatus)
</script>

<template>
  <div class="scheduler-page">
    <div class="section-title" style="margin-bottom: 16px; font-size: 1rem">智能调度控制</div>

    <div class="sched-grid">
      <!-- 调度状态卡片 -->
      <div class="tech-card" style="padding: 20px">
        <div class="section-title" style="margin-bottom: 14px">调度器状态</div>
        <div style="display: flex; align-items: center; gap: 16px; margin-bottom: 16px">
          <span style="color: var(--text-secondary); font-size: 0.875rem">自动调度</span>
          <button
            class="toggle-btn"
            :class="{ 'toggle-btn--on': autoEnabled }"
            @click="toggleAuto"
          >
            <span class="toggle-btn__dot"></span>
          </button>
          <span :style="{ color: autoEnabled ? '#34d399' : '#f87171', fontSize: '0.8125rem' }">
            {{ autoEnabled ? '已启用' : '已禁用' }}
          </span>
        </div>
        <div style="color: var(--text-muted); font-size: 0.8125rem; margin-bottom: 12px">
          当前时段: <span style="color: var(--accent-primary)">{{ timePeriod }}</span>
        </div>
        <button class="btn-tech btn-tech--primary" @click="runOnce" :disabled="scheduleLoading">
          {{ scheduleLoading ? '执行中...' : '手动执行一次调度' }}
        </button>
      </div>

      <!-- 功耗控制卡片 -->
      <div class="tech-card" style="padding: 20px">
        <div class="section-title" style="margin-bottom: 14px">手动功耗控制</div>
        <div v-for="gpu in store.gpus" :key="gpu.index" class="power-row">
          <span class="gpu-tag">GPU {{ gpu.index }}</span>
          <span class="stat-value" style="font-size: 0.875rem; min-width: 60px">{{ gpu.power_usage?.toFixed(0) }}W</span>
          <input
            type="range"
            min="100"
            max="350"
            :value="gpu.power_limit"
            @input="powerInputs[gpu.index] = $event.target.value"
            class="power-slider"
          />
          <input
            type="number"
            :value="powerInputs[gpu.index] || gpu.power_limit?.toFixed(0)"
            @input="powerInputs[gpu.index] = $event.target.value"
            min="100"
            max="350"
            class="power-input"
          />
          <button class="btn-tech" style="padding: 4px 12px; font-size: 0.75rem" @click="setPower(gpu.index)">设置</button>
        </div>
        <div v-if="!store.gpus.length" style="color: var(--text-muted); font-size: 0.8125rem; padding: 20px; text-align: center">等待GPU数据...</div>
      </div>

      <!-- 调度结果 -->
      <div class="tech-card" style="padding: 20px" v-if="scheduleResult">
        <div class="section-title" style="margin-bottom: 14px">调度执行结果</div>
        <div v-if="scheduleResult.ai_strategy" style="margin-bottom: 12px">
          <div style="color: var(--accent-primary); font-size: 0.8125rem; margin-bottom: 6px">AI策略摘要</div>
          <div style="color: var(--text-secondary); font-size: 0.8125rem">{{ scheduleResult.ai_strategy.summary }}</div>
          <div v-if="scheduleResult.ai_strategy.estimated_power_saving" style="color: #34d399; font-size: 0.8125rem; margin-top: 4px">
            预计节能: {{ scheduleResult.ai_strategy.estimated_power_saving }}W
          </div>
        </div>
        <div v-for="(r, i) in (scheduleResult.rule_results || []).concat(scheduleResult.ai_results || [])" :key="i"
             class="result-item" :class="r.success ? 'result-item--ok' : 'result-item--fail'">
          <span>{{ r.action }}</span>
          <span style="flex: 1; text-align: right">{{ r.success ? '成功' : '失败' }}</span>
        </div>
      </div>

      <!-- AI能耗报告 -->
      <div class="tech-card" style="padding: 20px">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px">
          <div class="section-title">AI 能耗分析报告</div>
          <button class="btn-tech" @click="loadReport" :disabled="reportLoading">
            {{ reportLoading ? '生成中...' : '生成报告' }}
          </button>
        </div>
        <div v-if="report" class="report-content" v-html="report.replace(/\n/g, '<br>')"></div>
        <div v-else style="color: var(--text-muted); font-size: 0.8125rem; text-align: center; padding: 20px">
          点击"生成报告"获取AI能耗分析
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.scheduler-page { max-width: 1400px; margin: 0 auto; }
.sched-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }

.toggle-btn {
  width: 44px; height: 24px; border-radius: 12px; border: none;
  background: rgba(255, 255, 255, 0.1); cursor: pointer;
  position: relative; transition: background 0.3s;
}
.toggle-btn--on { background: rgba(52, 211, 153, 0.3); }
.toggle-btn__dot {
  position: absolute; top: 3px; left: 3px;
  width: 18px; height: 18px; border-radius: 50%;
  background: #94a3b8; transition: all 0.3s;
}
.toggle-btn--on .toggle-btn__dot { left: 23px; background: #34d399; box-shadow: 0 0 8px rgba(52,211,153,0.4); }

.power-row {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.03);
}
.gpu-tag { font-size: 0.6875rem; font-weight: 600; color: var(--accent-primary); background: rgba(56,189,248,0.1); padding: 2px 8px; border-radius: 4px; }
.power-slider { flex: 1; accent-color: var(--accent-primary); }
.power-input {
  width: 60px; padding: 4px 6px; border-radius: 6px; border: 1px solid var(--border-color);
  background: transparent; color: var(--text-primary); font-size: 0.8125rem; text-align: center;
}

.result-item {
  display: flex; padding: 8px 12px; border-radius: 6px; font-size: 0.8125rem; margin-bottom: 4px;
}
.result-item--ok { background: rgba(52,211,153,0.08); color: #34d399; }
.result-item--fail { background: rgba(248,113,113,0.08); color: #f87171; }

.report-content {
  font-size: 0.8125rem; color: var(--text-secondary); line-height: 1.7;
  max-height: 400px; overflow-y: auto;
}
</style>

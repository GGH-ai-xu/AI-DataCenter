<script setup>
import { computed, ref } from 'vue'

import ControlCommandLedger from '../components/governance/ControlCommandLedger.vue'
import { buildControlCommandTimeline } from '../lib/controlCapabilityModels.js'
import { exportTextFile } from '../services/desktopExport.js'
import { exportFullGovernanceReport } from '../services/api.js'

const REPORT_FILENAME = 'governance-full-report.md'
const REPORT_MIME = 'text/markdown; charset=utf-8'

const props = defineProps({
  execution: {
    type: Object,
    default: () => ({}),
  },
  feedback: {
    type: Object,
    default: () => ({}),
  },
  governance: {
    type: Object,
    default: () => ({}),
  },
  reviewModel: {
    type: Object,
    default: () => ({}),
  },
  control: {
    type: Object,
    default: () => ({}),
  },
})

const exporting = ref(false)
const commandLedger = computed(() => buildControlCommandTimeline(
  props.governance.reviewState?.commandRecords || [],
))
const summary = computed(() => props.reviewModel.summary || {
  fairnessDelta: 0,
  failedActions: 0,
  totalActions: 0,
})

async function handleApprove(commandId, approved) {
  try {
    await props.control.approveCommand?.(
      commandId,
      approved,
      approved ? '治理复盘人工批准' : '治理复盘人工拒绝',
    )
    await props.governance.refreshReview?.({ force: true })
    props.feedback.showNotice?.(
      'ok',
      approved ? '命令已批准' : '命令已拒绝',
      `命令 ${commandId} 状态已更新。`,
    )
  } catch (error) {
    props.feedback.showNotice?.(
      'critical',
      '审批失败',
      error?.message || '请稍后重试',
    )
  }
}

async function exportReport() {
  exporting.value = true
  try {
    const response = await exportFullGovernanceReport(24)
    await exportTextFile(response.data, {
      filename: REPORT_FILENAME,
      mime: REPORT_MIME,
    })
    props.feedback.showNotice?.('ok', '综合治理报告已导出', '治理复盘报告已导出到本地。')
  } catch (error) {
    props.feedback.showNotice?.('critical', '报告导出失败', error?.message || '导出失败')
  } finally {
    exporting.value = false
  }
}
</script>

<template>
  <div class="review-grid">
    <section class="review-grid__ledger">
      <ControlCommandLedger :items="commandLedger" @approve="handleApprove" />
    </section>

    <section class="tech-card panel-card">
      <div class="panel-card__title">调度评估</div>
      <div class="panel-card__item">公平变化：{{ summary.fairnessDelta }}</div>
      <div class="panel-card__item">失败动作：{{ summary.failedActions }}</div>
      <div class="panel-card__item">动作总数：{{ summary.totalActions }}</div>
    </section>

    <section class="tech-card panel-card">
      <div class="panel-card__title">审计台账与导出</div>
      <div class="panel-card__item">最近 72 小时共 {{ summary.totalActions }} 条记录。</div>
      <button type="button" class="btn-tech btn-tech--primary" :disabled="exporting" @click="exportReport">
        {{ exporting ? '导出中...' : '导出综合治理报告' }}
      </button>
    </section>
  </div>
</template>

<style scoped>
.review-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) repeat(2, minmax(260px, 0.7fr));
  gap: 14px;
}

.review-grid__ledger {
  min-width: 0;
}

.panel-card {
  padding: 18px;
}

.panel-card__title {
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 12px;
}

.panel-card__item {
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border-color);
  font-size: 0.78rem;
  line-height: 1.7;
  color: var(--text-secondary);
}

.panel-card__item + .panel-card__item,
.panel-card__item + .btn-tech {
  margin-top: 10px;
}

@media (max-width: 1100px) {
  .review-grid {
    grid-template-columns: 1fr;
  }
}
</style>

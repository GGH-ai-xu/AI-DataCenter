<script setup>
import { computed, ref } from 'vue'

import { buildGovernanceReviewTimeline } from '../lib/governanceReviewModel.js'
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
})

const exporting = ref(false)
const timeline = computed(() => buildGovernanceReviewTimeline(props.governance.reviewState?.auditLogs || []))
const summary = computed(() => props.reviewModel.summary || {
  fairnessDelta: 0,
  failedActions: 0,
  totalActions: 0,
})

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
    <section class="tech-card panel-card">
      <div class="panel-card__title">最近治理结果</div>
      <div v-for="item in timeline" :key="item.id" class="panel-card__item">
        {{ item.createdAtLabel }} · {{ item.actionLabel }} · 风险 {{ item.riskLabel }}
      </div>
      <div v-if="!timeline.length" class="panel-card__item">最近没有新的治理动作。</div>
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
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
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

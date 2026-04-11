<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  items: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['approve'])

const statusFilter = ref('all')
const approvalFilter = ref('all')
const expandedCommandId = ref('')

const filteredItems = computed(() => props.items.filter((item) => {
  const statusMatched = statusFilter.value === 'all' || item.state === statusFilter.value
  const approvalMatched = approvalFilter.value === 'all' || item.approvalState === approvalFilter.value
  return statusMatched && approvalMatched
}))

function toggleExpanded(commandId) {
  expandedCommandId.value = expandedCommandId.value === commandId ? '' : commandId
}
</script>

<template>
  <section class="tech-card control-command-ledger">
    <div class="control-command-ledger__head">
      <div>
        <div class="panel-card__title">命令账本</div>
        <div class="control-command-ledger__hint">统一查看人工控制命令、审批状态与执行结果。</div>
      </div>

      <div class="control-command-ledger__filters">
        <label>
          <span>状态</span>
          <select v-model="statusFilter">
            <option value="all">全部</option>
            <option value="queued">排队中</option>
            <option value="awaiting_approval">待审批</option>
            <option value="succeeded">已完成</option>
            <option value="failed">执行失败</option>
            <option value="rejected">已拒绝</option>
          </select>
        </label>
        <label>
          <span>审批</span>
          <select v-model="approvalFilter">
            <option value="all">全部</option>
            <option value="not_required">无需审批</option>
            <option value="approved">已批准</option>
            <option value="pending">待审批</option>
            <option value="rejected">已拒绝</option>
          </select>
        </label>
      </div>
    </div>

    <div v-if="filteredItems.length" class="control-command-ledger__rows">
      <article
        v-for="item in filteredItems"
        :key="item.commandId || item.id"
        class="control-command-row"
      >
        <div class="control-command-row__head">
          <div class="control-command-row__title">
            <strong>{{ item.capabilityName || item.actionLabel }}</strong>
            <span>{{ item.createdAtLabel }}</span>
            <span>{{ item.sourceLabel }}</span>
          </div>
          <div class="control-command-row__badges">
            <span>{{ item.riskLabel }}</span>
            <span>{{ item.approvalLabel }}</span>
            <span>{{ item.stateLabel }}</span>
          </div>
        </div>

        <div class="control-command-row__summary">
          <span>{{ item.argumentSummary }}</span>
          <span>{{ item.resultSummary || item.errorMessage || '暂无执行摘要。' }}</span>
        </div>

        <div class="control-command-row__actions">
          <button
            v-if="item.hasDetails"
            type="button"
            class="btn-tech"
            @click="toggleExpanded(item.commandId)"
          >
            {{ expandedCommandId === item.commandId ? '收起详情' : '展开详情' }}
          </button>
          <button
            v-if="item.canApprove"
            type="button"
            class="btn-tech btn-tech--primary"
            @click="emit('approve', item.commandId, true)"
          >
            批准
          </button>
          <button
            v-if="item.canApprove"
            type="button"
            class="btn-tech"
            @click="emit('approve', item.commandId, false)"
          >
            拒绝
          </button>
        </div>

        <div v-if="expandedCommandId === item.commandId" class="control-command-row__details">
          <div><strong>来源：</strong>{{ item.sourceLabel }}</div>
          <div><strong>参数：</strong></div>
          <pre>{{ item.argumentsPreview }}</pre>
          <div v-if="item.resultSummary"><strong>执行摘要：</strong>{{ item.resultSummary }}</div>
          <div v-if="item.errorMessage"><strong>错误详情：</strong>{{ item.errorMessage }}</div>
        </div>
      </article>
    </div>

    <div v-else class="control-command-ledger__empty">最近没有控制命令记录。</div>
  </section>
</template>

<style scoped>
.control-command-ledger { display: grid; gap: 14px; padding: 18px; }
.control-command-ledger__head, .control-command-row__head, .control-command-row__actions {
  display: flex; gap: 12px; align-items: center; justify-content: space-between;
}
.control-command-ledger__filters, .control-command-row__title, .control-command-row__badges, .control-command-row__summary {
  display: flex; gap: 8px 10px; flex-wrap: wrap; align-items: center;
}
.control-command-ledger__filters label { display: grid; gap: 4px; font-size: 0.74rem; color: var(--text-muted); }
.control-command-ledger__filters select {
  min-width: 112px; border-radius: 10px; border: 1px solid var(--border-color); background: var(--bg-surface);
  color: var(--text-primary); padding: 8px 10px;
}
.control-command-ledger__hint, .control-command-row__summary, .control-command-ledger__empty, .control-command-row__details {
  font-size: 0.78rem; line-height: 1.7; color: var(--text-secondary);
}
.control-command-ledger__rows { display: grid; gap: 10px; }
.control-command-row {
  display: grid; gap: 8px; padding: 12px 14px; border-radius: 14px; border: 1px solid var(--border-color);
  background: var(--bg-surface);
}
.control-command-row__title span, .control-command-row__badges span {
  font-size: 0.74rem; color: var(--text-muted); padding: 2px 8px; border-radius: 999px; background: rgba(255, 255, 255, 0.04);
}
.control-command-row__details {
  display: grid; gap: 8px; padding-top: 8px; border-top: 1px dashed var(--border-color);
}
.control-command-row__details pre {
  margin: 0; padding: 10px 12px; border-radius: 12px; background: rgba(9, 14, 22, 0.72);
  border: 1px solid var(--border-color); overflow: auto; color: var(--text-secondary);
}
.control-command-ledger__empty {
  padding: 14px 16px; border-radius: 14px; border: 1px dashed var(--border-color); background: var(--bg-surface);
}

@media (max-width: 860px) {
  .control-command-ledger__head, .control-command-row__head, .control-command-row__actions { align-items: flex-start; flex-direction: column; }
}
</style>

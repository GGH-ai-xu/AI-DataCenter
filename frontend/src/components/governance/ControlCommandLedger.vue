<script setup>
const props = defineProps({
  items: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['approve'])
</script>

<template>
  <section class="tech-card control-command-ledger">
    <div class="control-command-ledger__head">
      <div>
        <div class="panel-card__title">命令账本</div>
        <div class="control-command-ledger__hint">统一查看人工控制命令、审批状态与执行结果。</div>
      </div>
    </div>

    <div v-if="props.items.length" class="control-command-ledger__rows">
      <article
        v-for="item in props.items"
        :key="item.commandId || item.id"
        class="control-command-row"
      >
        <div class="control-command-row__main">
          <strong>{{ item.capabilityName || item.actionLabel }}</strong>
          <span>{{ item.createdAtLabel }}</span>
          <span>{{ item.riskLabel }}</span>
          <span>{{ item.approvalLabel }}</span>
          <span>{{ item.stateLabel }}</span>
        </div>
        <div class="control-command-row__summary">
          {{ item.resultSummary || item.errorMessage || '暂无执行摘要。' }}
        </div>
        <div v-if="item.approvalState === 'pending'" class="control-command-row__actions">
          <button type="button" class="btn-tech btn-tech--primary" @click="emit('approve', item.commandId, true)">
            批准
          </button>
          <button type="button" class="btn-tech" @click="emit('approve', item.commandId, false)">
            拒绝
          </button>
        </div>
      </article>
    </div>

    <div v-else class="control-command-ledger__empty">
      最近没有控制命令记录。
    </div>
  </section>
</template>

<style scoped>
.control-command-ledger {
  display: grid;
  gap: 14px;
  padding: 18px;
}

.control-command-ledger__hint,
.control-command-row__summary,
.control-command-ledger__empty {
  font-size: 0.78rem;
  line-height: 1.7;
  color: var(--text-secondary);
}

.control-command-ledger__rows {
  display: grid;
  gap: 10px;
}

.control-command-row {
  display: grid;
  gap: 8px;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: var(--bg-surface);
}

.control-command-row__main,
.control-command-row__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 10px;
  align-items: center;
}

.control-command-row__main span {
  font-size: 0.74rem;
  color: var(--text-muted);
}

.control-command-row__actions {
  justify-content: flex-end;
}

.control-command-ledger__empty {
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px dashed var(--border-color);
  background: var(--bg-surface);
}
</style>

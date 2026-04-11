<script setup>
defineProps({
  reconcileBusy: {
    type: Boolean,
    default: false,
  },
  toggleBusy: {
    type: Boolean,
    default: false,
  },
  controller: {
    type: Object,
    default: () => ({}),
  },
})

defineEmits(['reconcile', 'jump-submit', 'open-drawer', 'toggle-auto'])
</script>

<template>
  <div class="cluster-console-toolbar">
    <div class="cluster-console-toolbar__status">
      <strong>{{ controller.enabled ? '自动调和已开启' : '自动调和已关闭' }}</strong>
      <span>{{ controller.intervalLabel || '未设置' }}</span>
      <span>最近 {{ controller.lastRunLabel || '未运行' }}</span>
      <span>{{ controller.summaryLabel || '暂无最近结果' }}</span>
    </div>
    <button
      type="button"
      class="btn-tech"
      :disabled="toggleBusy"
      @click="$emit('toggle-auto')"
    >
      {{ toggleBusy ? '更新中...' : (controller.toggleLabel || '开启自动调和') }}
    </button>
    <button
      type="button"
      class="btn-tech"
      :disabled="reconcileBusy"
      @click="$emit('reconcile')"
    >
      {{ reconcileBusy ? '调和中...' : '执行队列调和' }}
    </button>
    <button type="button" class="btn-tech btn-tech--primary" @click="$emit('jump-submit')">
      提交作业
    </button>
    <button type="button" class="btn-tech" @click="$emit('open-drawer')">
      高级集群操作
    </button>
  </div>
</template>

<style scoped>
.cluster-console-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.cluster-console-toolbar__status {
  min-width: 0;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.cluster-console-toolbar__status strong {
  color: var(--text-primary);
}

@media (max-width: 1100px) {
  .cluster-console-toolbar {
    justify-content: stretch;
    align-items: stretch;
    flex-wrap: wrap;
  }
}
</style>

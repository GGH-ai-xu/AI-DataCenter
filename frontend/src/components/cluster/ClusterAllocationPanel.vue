<script setup>
defineProps({
  allocationsByNode: {
    type: Array,
    default: () => [],
  },
})
</script>

<template>
  <section class="tech-card cluster-allocation-panel">
    <div class="cluster-section-heading">
      <h3>分配快照</h3>
      <p>按节点聚合当前 allocation，避免每条占过多高度。</p>
    </div>
    <div v-if="allocationsByNode.length" class="cluster-allocation-panel__groups">
      <article
        v-for="group in allocationsByNode"
        :key="group.nodeId"
        class="cluster-allocation-group"
      >
        <div class="cluster-allocation-group__node">{{ group.nodeId }}</div>
        <div class="cluster-allocation-group__items">
          <span
            v-for="item in group.allocations"
            :key="item.id"
            class="cluster-allocation-chip"
          >
            {{ item.jobId }} · {{ item.status }}
          </span>
        </div>
      </article>
    </div>
    <div v-else class="cluster-allocation-panel__empty">
      当前还没有 active allocation。
    </div>
  </section>
</template>

<style scoped>
.cluster-allocation-panel {
  display: grid;
  gap: 14px;
  padding: 18px;
}

.cluster-allocation-panel__groups {
  display: grid;
  gap: 12px;
}

.cluster-allocation-group {
  display: grid;
  gap: 10px;
  padding: 14px;
  border-radius: 16px;
  border: 1px solid var(--border-subtle);
  background: var(--bg-surface);
}

.cluster-allocation-group__node {
  font-size: 0.82rem;
  font-weight: 700;
  color: var(--text-primary);
}

.cluster-allocation-group__items {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.cluster-allocation-chip {
  padding: 6px 10px;
  border-radius: 999px;
  background: var(--bg-strong);
  color: var(--text-secondary);
  font-size: 0.78rem;
}

.cluster-allocation-panel__empty {
  padding: 16px;
  border-radius: 14px;
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: 0.84rem;
}
</style>

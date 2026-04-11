<script setup>
defineProps({
  allocationsByNode: {
    type: Array,
    default: () => [],
  },
  nodes: {
    type: Array,
    default: () => [],
  },
})

defineEmits(['release', 'toggle-drain'])
</script>

<template>
  <section class="tech-card cluster-allocation-panel">
    <div class="cluster-section-heading">
      <h3>分配快照</h3>
      <p>按节点聚合 allocation，并直接处理节点 drain 与 allocation 释放。</p>
    </div>
    <div v-if="nodes.length" class="cluster-allocation-panel__groups">
      <article
        v-for="node in nodes"
        :key="node.id"
        class="cluster-allocation-group"
      >
        <div class="cluster-allocation-group__head">
          <div>
            <div class="cluster-allocation-group__node">{{ node.label }}</div>
            <div class="cluster-allocation-group__meta">{{ node.id }} · {{ node.state }} · {{ node.drainState }}</div>
          </div>
          <button
            type="button"
            class="btn-tech"
            @click="$emit('toggle-drain', { nodeId: node.id, drainState: node.drainState })"
          >
            {{ node.drainState === 'drained' ? '恢复节点' : '排空节点' }}
          </button>
        </div>

        <div class="cluster-allocation-group__items">
          <template
            v-for="item in allocationsByNode.find((group) => group.nodeId === node.id)?.allocations || []"
            :key="item.id"
          >
            <span class="cluster-allocation-chip">
              {{ item.jobId }} · {{ item.status }}
              <button
                v-if="item.releaseable"
                type="button"
                class="cluster-allocation-chip__button"
                @click="$emit('release', item.id)"
              >
                释放
              </button>
            </span>
          </template>
          <span
            v-if="!(allocationsByNode.find((group) => group.nodeId === node.id)?.allocations || []).length"
            class="cluster-allocation-group__empty"
          >
            当前节点没有 active allocation。
          </span>
        </div>
      </article>
    </div>
    <div v-else class="cluster-allocation-panel__empty">当前还没有可展示的节点状态。</div>
  </section>
</template>

<style scoped>
.cluster-allocation-panel, .cluster-allocation-panel__groups, .cluster-allocation-group { display: grid; gap: 12px; }
.cluster-allocation-panel { padding: 18px; }
.cluster-allocation-group { padding: 14px; border-radius: 16px; border: 1px solid var(--border-subtle); background: var(--bg-surface); }
.cluster-allocation-group__head { display: flex; gap: 12px; align-items: center; justify-content: space-between; }
.cluster-allocation-group__node { font-size: 0.82rem; font-weight: 700; color: var(--text-primary); }
.cluster-allocation-group__meta, .cluster-allocation-panel__empty, .cluster-allocation-group__empty { font-size: 0.78rem; color: var(--text-secondary); }
.cluster-allocation-group__items { display: flex; flex-wrap: wrap; gap: 8px; }
.cluster-allocation-chip {
  display: inline-flex; gap: 8px; align-items: center; padding: 6px 10px; border-radius: 999px;
  background: var(--bg-strong); color: var(--text-secondary); font-size: 0.78rem;
}
.cluster-allocation-chip:has(.cluster-allocation-chip__button) {
  color: var(--text-primary);
}
.cluster-allocation-chip__button { border: none; background: transparent; color: var(--text-primary); cursor: pointer; }
</style>

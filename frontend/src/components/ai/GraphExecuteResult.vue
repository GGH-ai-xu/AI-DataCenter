<script setup>
const props = defineProps({
  summary: {
    type: Object,
    required: true,
  },
  executionResult: {
    type: Object,
    default: null,
  },
})
</script>

<template>
  <section class="tech-card graph-result">
    <div class="graph-result__head">
      <div>
        <div class="graph-result__eyebrow">执行结果</div>
        <div class="graph-result__title">图库状态与最近一次写入结果</div>
      </div>
      <span class="status-badge" :class="props.summary.neo4j_connected ? 'status-badge--ok' : 'status-badge--warning'">
        {{ props.summary.neo4j_connected ? '图库在线' : '图库离线' }}
      </span>
    </div>

    <div class="graph-result__board">
      <div class="graph-result__item">
        <span>当前论文数</span>
        <strong>{{ props.summary.paper_count || 0 }}</strong>
      </div>
      <div class="graph-result__item">
        <span>当前节点总数</span>
        <strong>{{ props.summary.node_count || 0 }}</strong>
      </div>
      <div class="graph-result__item">
        <span>当前关系总数</span>
        <strong>{{ props.summary.relation_count || 0 }}</strong>
      </div>
      <div class="graph-result__item">
        <span>状态说明</span>
        <strong>{{ props.summary.message || '等待写入' }}</strong>
      </div>
    </div>

    <div v-if="!props.executionResult" class="graph-result__empty">
      还没有执行写入。生成草稿后，确认 Neo4j 已连接，再点击“写入 Neo4j”。
    </div>

    <div v-else class="graph-result__log">
      <div class="graph-result__log-item">
        <span>写入结果</span>
        <strong>{{ props.executionResult.message || '完成' }}</strong>
      </div>
      <div class="graph-result__log-item">
        <span>新建节点</span>
        <strong>{{ props.executionResult.nodes_created || 0 }}</strong>
      </div>
      <div class="graph-result__log-item">
        <span>新建关系</span>
        <strong>{{ props.executionResult.relationships_created || 0 }}</strong>
      </div>
      <div class="graph-result__log-item">
        <span>属性更新</span>
        <strong>{{ props.executionResult.properties_set || 0 }}</strong>
      </div>
    </div>
  </section>
</template>

<style scoped>
.graph-result {
  padding: 20px 22px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.graph-result__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.graph-result__eyebrow {
  font-size: 0.74rem;
  letter-spacing: 0.12em;
  color: var(--text-muted);
  text-transform: uppercase;
}

.graph-result__title {
  margin-top: 8px;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.graph-result__board,
.graph-result__log {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.graph-result__item,
.graph-result__log-item,
.graph-result__empty {
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  box-shadow: var(--shadow-card);
}

.graph-result__item span,
.graph-result__log-item span,
.graph-result__empty {
  font-size: 0.74rem;
  color: var(--text-muted);
  line-height: 1.7;
}

.graph-result__item strong,
.graph-result__log-item strong {
  display: block;
  margin-top: 6px;
  font-size: 0.92rem;
  color: var(--text-primary);
}

@media (max-width: 960px) {
  .graph-result__board,
  .graph-result__log {
    grid-template-columns: 1fr;
  }
}
</style>

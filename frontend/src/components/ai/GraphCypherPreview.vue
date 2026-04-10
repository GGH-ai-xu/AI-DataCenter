<script setup>
const props = defineProps({
  draftResult: {
    type: Object,
    default: null,
  },
})
</script>

<template>
  <section class="tech-card graph-preview">
    <div class="graph-preview__head">
      <div>
        <div class="graph-preview__eyebrow">草稿预览</div>
        <div class="graph-preview__title">固定 schema + 可审查 Cypher</div>
      </div>
      <div v-if="props.draftResult?.summary" class="ink-inline-meta">
        <span class="status-badge">{{ props.draftResult.summary.node_count }} 个节点</span>
        <span class="status-badge">{{ props.draftResult.summary.relation_count }} 条关系</span>
      </div>
    </div>

    <div v-if="!props.draftResult" class="graph-preview__empty">
      先输入论文标题和内容，再生成图谱草稿。这里会展示结构摘要和可执行的 Cypher。
    </div>

    <template v-else>
      <div class="graph-preview__summary">
        <div class="graph-preview__summary-item">
          <span>标题</span>
          <strong>{{ props.draftResult.summary?.title || '-' }}</strong>
        </div>
        <div class="graph-preview__summary-item">
          <span>节点类型</span>
          <strong>{{ Object.keys(props.draftResult.summary?.labels || {}).join(' / ') || '-' }}</strong>
        </div>
      </div>

      <div v-if="props.draftResult.warnings?.length" class="graph-preview__warnings">
        <div
          v-for="(warning, index) in props.draftResult.warnings"
          :key="index"
          class="graph-preview__warning"
        >
          {{ warning }}
        </div>
      </div>

      <div class="graph-preview__code-wrap">
        <pre class="graph-preview__code"><code>{{ props.draftResult.cypher }}</code></pre>
      </div>
    </template>
  </section>
</template>

<style scoped>
.graph-preview {
  padding: 20px 22px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.graph-preview__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.graph-preview__eyebrow {
  font-size: 0.74rem;
  letter-spacing: 0.12em;
  color: var(--text-muted);
  text-transform: uppercase;
}

.graph-preview__title {
  margin-top: 8px;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.graph-preview__empty,
.graph-preview__warning {
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-muted);
  line-height: 1.7;
}

.graph-preview__summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.graph-preview__summary-item {
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
}

.graph-preview__summary-item span {
  font-size: 0.72rem;
  color: var(--text-muted);
}

.graph-preview__summary-item strong {
  display: block;
  margin-top: 6px;
  font-size: 0.92rem;
  color: var(--text-primary);
}

.graph-preview__warnings {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.graph-preview__warning {
  color: var(--state-warning-text);
  border-color: var(--state-warning-border);
  background: var(--state-warning-bg);
}

.graph-preview__code-wrap {
  border-radius: 16px;
  border: 1px solid var(--border-color);
  background: var(--field-background);
  overflow: hidden;
}

.graph-preview__code {
  margin: 0;
  padding: 16px;
  overflow: auto;
  font-size: 0.78rem;
  line-height: 1.7;
  color: var(--text-primary);
  font-family: 'Consolas', 'SFMono-Regular', 'Courier New', monospace;
}

@media (max-width: 960px) {
  .graph-preview__summary {
    grid-template-columns: 1fr;
  }
}
</style>

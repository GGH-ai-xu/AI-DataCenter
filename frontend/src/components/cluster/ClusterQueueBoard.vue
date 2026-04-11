<script setup>
defineProps({
  queues: {
    type: Array,
    default: () => [],
  },
})
</script>

<template>
  <section class="tech-card cluster-queue-board">
    <div class="cluster-section-heading">
      <h3>队列概览</h3>
      <p>保留最关键的准入状态、并发上限与阻塞原因。</p>
    </div>
    <div class="cluster-queue-board__grid">
      <article
        v-for="queue in queues"
        :key="queue.id"
        class="cluster-queue-card"
      >
        <div class="cluster-queue-card__top">
          <strong>{{ queue.name }}</strong>
          <span class="status-badge" :class="queue.state === 'active' ? 'status-badge--ok' : 'status-badge--warning'">
            {{ queue.state }}
          </span>
        </div>
        <div class="cluster-queue-card__metrics">
          <span>等待 {{ queue.queuedJobs }}</span>
          <span>运行 {{ queue.runningJobs }}</span>
          <span v-if="queue.dispatchingJobs">调和中 {{ queue.dispatchingJobs }}</span>
          <span v-if="queue.failedJobs">失败 {{ queue.failedJobs }}</span>
          <span>{{ queue.concurrencyLabel }}</span>
          <span v-if="queue.blockedJobs">阻塞 {{ queue.blockedJobs }}</span>
          <span>默认优先级 {{ queue.defaultPriority }}</span>
        </div>
        <p v-if="queue.waitReasonSummary" class="cluster-queue-card__reason">
          {{ queue.waitReasonSummary }}
        </p>
      </article>
    </div>
  </section>
</template>

<style scoped>
.cluster-queue-board {
  display: grid;
  gap: 14px;
  padding: 18px;
}

.cluster-section-heading h3 {
  margin: 0;
  font-size: 0.96rem;
  color: var(--text-primary);
}

.cluster-section-heading p {
  margin: 6px 0 0;
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.cluster-queue-board__grid {
  display: grid;
  gap: 12px;
}

.cluster-queue-card {
  display: grid;
  gap: 8px;
  padding: 14px;
  border-radius: 16px;
  border: 1px solid var(--border-subtle);
  background: var(--bg-surface);
}

.cluster-queue-card__top,
.cluster-queue-card__metrics {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}

.cluster-queue-card__metrics {
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.cluster-queue-card__reason {
  margin: 0;
  font-size: 0.78rem;
  color: var(--text-secondary);
  line-height: 1.45;
}
</style>

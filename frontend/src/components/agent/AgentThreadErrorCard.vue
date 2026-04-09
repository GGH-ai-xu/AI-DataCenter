<script setup>
defineProps({
  item: { type: Object, required: true },
})
</script>

<template>
  <article class="tech-card agent-thread-card agent-thread-card--danger">
    <strong>{{ item.summary }}</strong>
  </article>
</template>

<style scoped>
.agent-thread-card {
  padding: 14px;
}

.agent-thread-card--danger {
  border-color: var(--state-danger-border);
}
</style>

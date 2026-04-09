<script setup>
defineProps({
  item: { type: Object, required: true },
})
</script>

<template>
  <article class="tech-card agent-thread-card">
    <span>{{ item.summary }}</span>
  </article>
</template>

<style scoped>
.agent-thread-card {
  padding: 14px;
}
</style>

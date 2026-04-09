<script setup>
defineProps({
  item: { type: Object, required: true },
})
</script>

<template>
  <article class="tech-card agent-thread-card">
    <strong>{{ item.summary }}</strong>
  </article>
</template>

<style scoped>
.agent-thread-card {
  padding: 14px;
}
</style>

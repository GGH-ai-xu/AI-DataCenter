<script setup>
defineProps({
  item: { type: Object, required: true },
})

const emit = defineEmits(['approve', 'reject'])
</script>

<template>
  <article class="tech-card agent-thread-card">
    <strong>{{ item.summary }}</strong>
    <div class="ink-inline-meta">
      <button class="btn-tech btn-tech--primary" @click="emit('approve', item)">
        批准
      </button>
      <button class="btn-tech" @click="emit('reject', item)">
        拒绝
      </button>
    </div>
  </article>
</template>

<style scoped>
.agent-thread-card {
  display: grid;
  gap: 12px;
  padding: 14px;
}
</style>

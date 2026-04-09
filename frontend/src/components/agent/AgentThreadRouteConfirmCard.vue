<script setup>
defineProps({
  item: { type: Object, required: true },
})

const emit = defineEmits(['choose'])
</script>

<template>
  <article class="tech-card agent-thread-card">
    <strong>这条输入还需要确认意图</strong>
    <p>{{ item.message }}</p>
    <div class="ink-inline-meta">
      <button class="btn-tech" @click="emit('choose', 'chat')">
        按解释处理
      </button>
      <button class="btn-tech btn-tech--primary" @click="emit('choose', 'runtime')">
        按执行处理
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

.agent-thread-card p {
  margin: 0;
  color: var(--text-secondary);
}
</style>

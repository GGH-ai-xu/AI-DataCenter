<script setup>
defineProps({
  model: { type: Object, required: true },
})
</script>

<template>
  <header class="agent-workbench-topbar tech-card">
    <span class="status-badge">{{ model.modeLabel }}</span>
    <span class="status-badge">{{ model.statusLabel }}</span>
    <span class="status-badge">{{ model.approvalLabel }}</span>
  </header>
</template>

<style scoped>
.agent-workbench-topbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  padding: 12px 14px;
}
</style>

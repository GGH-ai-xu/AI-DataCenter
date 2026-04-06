<script setup>
const props = defineProps({
  currentTime: {
    type: String,
    required: true,
  },
})
</script>

<template>
  <section class="app-sidebar-dock">
    <span class="app-sidebar-dock__label">时间</span>
    <strong class="app-sidebar-dock__value">{{ props.currentTime }}</strong>
  </section>
</template>

<style scoped>
.app-sidebar-dock {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 18px;
  border: 1px solid rgba(58, 95, 75, 0.08);
  background: rgba(255, 252, 247, 0.9);
}

.app-sidebar-dock__label {
  font-size: 0.7rem;
  letter-spacing: 0.08em;
  color: #8b948b;
}

.app-sidebar-dock__value {
  font-size: 0.86rem;
  line-height: 1.4;
  color: #2f6a46;
  text-align: right;
}
</style>

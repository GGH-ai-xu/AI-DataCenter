<script setup>
const props = defineProps({
  currentTime: {
    type: String,
    required: true,
  },
  telemetry: {
    type: Array,
    default: () => [],
  },
})
</script>

<template>
  <section class="app-sidebar-dock">
    <div class="app-sidebar-dock__copy">
      <span class="app-sidebar-dock__label">北京时间</span>
      <strong class="app-sidebar-dock__value">{{ props.currentTime }}</strong>
    </div>
    <span class="app-sidebar-dock__badge">Live</span>
    <div v-if="props.telemetry.length" class="app-sidebar-dock__grid">
      <div v-for="item in props.telemetry" :key="item.label" class="app-sidebar-dock__item">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </div>
    </div>
  </section>
</template>

<style scoped>
.app-sidebar-dock {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: #121a24;
  box-shadow: 0 18px 44px rgba(0, 0, 0, 0.28);
}

.app-sidebar-dock__copy {
  display: grid;
  gap: 4px;
}

.app-sidebar-dock__label {
  font-family: var(--font-seal);
  font-size: 0.66rem;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.app-sidebar-dock__value {
  font-size: 0.9rem;
  line-height: 1.4;
  color: var(--text-primary);
}

.app-sidebar-dock__badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-width: 52px;
  min-height: 30px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid rgba(94, 106, 210, 0.24);
  background: rgba(94, 106, 210, 0.14);
  color: #dbe0ff;
  font-family: var(--font-seal);
  font-size: 0.7rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.app-sidebar-dock__badge::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: #5e6ad2;
}

.app-sidebar-dock__grid {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.app-sidebar-dock__item {
  display: grid;
  gap: 4px;
  padding: 12px;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: #101821;
}

.app-sidebar-dock__item span {
  font-size: 0.7rem;
  color: var(--text-muted);
}

.app-sidebar-dock__item strong {
  font-size: 0.92rem;
  color: var(--text-primary);
}
</style>

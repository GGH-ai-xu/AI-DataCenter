<script setup>
defineProps({
  modelValue: {
    type: String,
    required: true,
  },
  items: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['update:modelValue'])
</script>

<template>
  <div class="alert-archive-type-tabs">
    <button
      v-for="item in items"
      :key="item.key"
      type="button"
      class="alert-archive-type-tabs__item"
      :class="{ 'alert-archive-type-tabs__item--active': modelValue === item.key }"
      @click="emit('update:modelValue', item.key)"
    >
      <span class="alert-archive-type-tabs__label">{{ item.label }}</span>
      <strong class="alert-archive-type-tabs__count">{{ item.count }}</strong>
      <span class="alert-archive-type-tabs__desc">{{ item.desc }}</span>
    </button>
  </div>
</template>

<style scoped>
.alert-archive-type-tabs {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(168px, 1fr));
  gap: 12px;
}

.alert-archive-type-tabs__item {
  display: grid;
  gap: 4px;
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid var(--border-color);
  background: rgba(255, 255, 255, 0.03);
  text-align: left;
  color: var(--text-secondary);
  transition: border-color 0.18s ease, background 0.18s ease, transform 0.18s ease;
}

.alert-archive-type-tabs__item:hover {
  border-color: rgba(0, 212, 170, 0.18);
  transform: translateY(-1px);
}

.alert-archive-type-tabs__item--active {
  border-color: rgba(0, 212, 170, 0.24);
  background: rgba(0, 212, 170, 0.08);
}

.alert-archive-type-tabs__label {
  font-size: 0.84rem;
  font-weight: 600;
  color: var(--text-primary);
}

.alert-archive-type-tabs__count {
  font-size: 1.12rem;
  line-height: 1.1;
  color: var(--accent-primary);
}

.alert-archive-type-tabs__desc {
  font-size: 0.74rem;
  line-height: 1.6;
  color: var(--text-muted);
  overflow-wrap: anywhere;
}

@media (max-width: 720px) {
  .alert-archive-type-tabs {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 520px) {
  .alert-archive-type-tabs {
    grid-template-columns: 1fr;
  }
}
</style>

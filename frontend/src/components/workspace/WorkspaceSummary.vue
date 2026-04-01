<script setup>
defineProps({
  eyebrow: {
    type: String,
    default: '',
  },
  title: {
    type: String,
    required: true,
  },
  description: {
    type: String,
    default: '',
  },
})
</script>

<template>
  <section class="workspace-summary tech-card">
    <div v-if="eyebrow" class="workspace-summary__eyebrow">{{ eyebrow }}</div>
    <div class="workspace-summary__top">
      <div class="workspace-summary__main">
        <h2 class="workspace-summary__title">{{ title }}</h2>
        <p v-if="description" class="workspace-summary__desc">{{ description }}</p>
      </div>
      <div v-if="$slots.meta" class="workspace-summary__meta">
        <slot name="meta" />
      </div>
    </div>
    <div v-if="$slots.default" class="workspace-summary__body">
      <slot />
    </div>
  </section>
</template>

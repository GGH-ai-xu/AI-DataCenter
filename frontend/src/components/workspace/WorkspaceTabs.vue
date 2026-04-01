<script setup>
defineProps({
  items: {
    type: Array,
    required: true,
  },
  modelValue: {
    type: String,
    required: true,
  },
})

const emit = defineEmits(['update:modelValue'])
</script>

<template>
  <div class="workspace-tabs">
    <button
      v-for="item in items"
      :key="item.key"
      type="button"
      class="workspace-tab"
      :class="{ 'workspace-tab--active': modelValue === item.key }"
      @click="emit('update:modelValue', item.key)"
    >
      <span class="workspace-tab__label">{{ item.label }}</span>
      <span v-if="item.desc" class="workspace-tab__desc">{{ item.desc }}</span>
    </button>
  </div>
</template>

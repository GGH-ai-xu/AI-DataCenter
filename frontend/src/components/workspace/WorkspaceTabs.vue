<script setup>
import { computed } from 'vue'

const props = defineProps({
  items: {
    type: Array,
    required: true,
  },
  modelValue: {
    type: String,
    required: true,
  },
  orientation: {
    type: String,
    default: 'horizontal',
  },
})

const emit = defineEmits(['update:modelValue'])
const rootClass = computed(() => ({
  'workspace-tabs--vertical': props.orientation === 'vertical',
}))
</script>

<template>
  <div class="workspace-tabs" :class="rootClass">
    <button
      v-for="item in props.items"
      :key="item.key"
      type="button"
      class="workspace-tab"
      :class="{ 'workspace-tab--active': props.modelValue === item.key }"
      @click="emit('update:modelValue', item.key)"
    >
      <span class="workspace-tab__label">{{ item.label }}</span>
      <span v-if="item.desc" class="workspace-tab__desc">{{ item.desc }}</span>
    </button>
  </div>
</template>

<script setup>
defineProps({
  inputText: { type: String, required: true },
  quickPrompts: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['update:inputText', 'submit', 'usePrompt'])
</script>

<template>
  <footer class="agent-composer tech-card">
    <textarea
      class="agent-composer__input"
      :value="inputText"
      rows="4"
      @input="emit('update:inputText', $event.target.value)"
    />
    <div class="agent-composer__chips">
      <button
        v-for="item in quickPrompts"
        :key="item"
        type="button"
        class="btn-tech"
        @click="emit('usePrompt', item)"
      >
        {{ item }}
      </button>
    </div>
    <button
      type="button"
      class="btn-tech btn-tech--primary"
      :disabled="disabled"
      @click="emit('submit')"
    >
      发送
    </button>
  </footer>
</template>

<style scoped>
.agent-composer {
  display: grid;
  gap: 12px;
  padding: 14px;
}

.agent-composer__input {
  min-height: 108px;
  resize: vertical;
}

.agent-composer__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>

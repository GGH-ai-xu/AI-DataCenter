<script setup>
import { nextTick, onMounted, ref, watch } from 'vue'

const props = defineProps({
  inputText: { type: String, required: true },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['update:inputText', 'submit'])
const textareaRef = ref(null)

function resizeTextarea() {
  const element = textareaRef.value
  if (!element) return
  element.style.height = 'auto'
  element.style.height = `${Math.min(element.scrollHeight, 320)}px`
}

function handleInput(event) {
  emit('update:inputText', event.target.value)
  resizeTextarea()
}

onMounted(resizeTextarea)

watch(
  () => props.inputText,
  async () => {
    await nextTick()
    resizeTextarea()
  },
)
</script>

<template>
  <footer class="agent-composer">
    <textarea
      ref="textareaRef"
      class="agent-composer__input"
      :value="inputText"
      rows="1"
      @input="handleInput"
    />
    <button
      type="button"
      class="btn-tech btn-tech--primary"
      :disabled="disabled || !inputText.trim()"
      @click="emit('submit')"
    >
      发送
    </button>
  </footer>
</template>

<style scoped>
.agent-composer {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: end;
  gap: 12px;
  padding: 0;
}

.agent-composer__input {
  width: 100%;
  min-height: 56px;
  max-height: 320px;
  padding: 14px 16px;
  border: 1px solid color-mix(in srgb, var(--border-color) 92%, transparent);
  border-radius: 16px;
  background: color-mix(in srgb, var(--bg-card) 78%, var(--bg-surface));
  resize: none;
  overflow-y: hidden;
}

.agent-composer .btn-tech {
  min-height: 44px;
  padding-inline: 18px;
}
</style>

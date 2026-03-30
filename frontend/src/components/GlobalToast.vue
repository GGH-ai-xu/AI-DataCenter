<template>
  <Teleport to="body">
    <TransitionGroup name="toast-slide" tag="div" class="toast-container">
      <div
        v-for="item in toasts"
        :key="item.id"
        :class="['toast-item', `toast-${item.type}`]"
        @click="dismiss(item.id)"
      >
        <span class="toast-icon">{{ iconMap[item.type] || '●' }}</span>
        <span class="toast-msg">{{ item.message }}</span>
      </div>
    </TransitionGroup>
  </Teleport>
</template>

<script setup>
import { ref } from 'vue'

const toasts = ref([])
let idCounter = 0
const iconMap = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' }

function show(message, type = 'info', duration = 3500) {
  const id = ++idCounter
  toasts.value.push({ id, message, type })
  setTimeout(() => dismiss(id), duration)
}

function dismiss(id) {
  toasts.value = toasts.value.filter(t => t.id !== id)
}

defineExpose({ show })
</script>

<style scoped>
.toast-container {
  position: fixed;
  top: 16px;
  right: 16px;
  z-index: 99999;
  display: flex;
  flex-direction: column;
  gap: 8px;
  pointer-events: none;
}
.toast-item {
  pointer-events: auto;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 18px;
  border-radius: 8px;
  font-size: 0.85rem;
  color: #fff;
  backdrop-filter: blur(12px);
  box-shadow: 0 4px 16px rgba(0,0,0,.25);
  cursor: pointer;
  max-width: 380px;
  word-break: break-word;
}
.toast-success { background: rgba(46,139,87,.92); }
.toast-error   { background: rgba(200,50,50,.92); }
.toast-warning { background: rgba(184,134,11,.92); }
.toast-info    { background: rgba(60,90,130,.92); }
.toast-icon    { font-size: 1rem; flex-shrink: 0; }

.toast-slide-enter-active,
.toast-slide-leave-active {
  transition: all .3s ease;
}
.toast-slide-enter-from {
  opacity: 0;
  transform: translateX(60px);
}
.toast-slide-leave-to {
  opacity: 0;
  transform: translateX(60px);
}
</style>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'

const THEME_OPTIONS = Object.freeze([
  { value: 'system', label: '系统', detail: '跟随设备', icon: '系' },
  { value: 'dark', label: '深色', detail: '专注夜间', icon: '深' },
  { value: 'light', label: '亮色', detail: '适合白天', icon: '亮' },
])

const props = defineProps({
  preference: { type: String, required: true },
  resolvedTheme: { type: String, required: true },
  collapsed: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
})

const emit = defineEmits(['update:preference'])
const rootRef = ref(null)
const menuOpen = ref(false)

const isPopoverMode = computed(() => props.collapsed || props.compact)
const activeOption = computed(() => (
  THEME_OPTIONS.find((option) => option.value === props.preference) || THEME_OPTIONS[0]
))
const resolvedLabel = computed(() => (props.resolvedTheme === 'light' ? '亮色生效' : '深色生效'))

function selectOption(value) {
  emit('update:preference', value)
  menuOpen.value = false
}

function toggleMenu() {
  menuOpen.value = !menuOpen.value
}

function handlePointerDown(event) {
  if (!rootRef.value?.contains(event.target)) {
    menuOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('pointerdown', handlePointerDown)
})

onUnmounted(() => {
  document.removeEventListener('pointerdown', handlePointerDown)
})
</script>

<template>
  <div
    ref="rootRef"
    class="theme-mode-switch"
    :class="{
      'theme-mode-switch--collapsed': collapsed,
      'theme-mode-switch--compact': compact,
      'theme-mode-switch--popover': isPopoverMode,
    }"
  >
    <template v-if="!isPopoverMode">
      <div class="theme-mode-switch__summary">
        <span class="theme-mode-switch__eyebrow">主题</span>
        <strong class="theme-mode-switch__resolved">{{ resolvedLabel }}</strong>
      </div>
      <div class="theme-mode-switch__group theme-mode-switch__group--inline">
        <button
          v-for="option in THEME_OPTIONS"
          :key="option.value"
          type="button"
          class="theme-mode-switch__option"
          :class="{ 'theme-mode-switch__option--active': preference === option.value }"
          @click="selectOption(option.value)"
        >
          <span class="theme-mode-switch__option-icon" aria-hidden="true">{{ option.icon }}</span>
          <span class="theme-mode-switch__option-label">{{ option.label }}</span>
        </button>
      </div>
    </template>

    <template v-else>
      <button
        type="button"
        class="theme-mode-switch__trigger"
        :class="{ 'theme-mode-switch__trigger--open': menuOpen }"
        :title="collapsed ? `主题：${activeOption.label}` : ''"
        :aria-label="`主题：${activeOption.label}`"
        @click="toggleMenu"
      >
        <span class="theme-mode-switch__trigger-icon" aria-hidden="true">{{ activeOption.icon }}</span>
        <span
          v-if="!collapsed"
          class="theme-mode-switch__trigger-copy"
        >
          主题 · {{ activeOption.label }}
        </span>
      </button>
      <div
        v-if="menuOpen"
        class="theme-mode-switch__menu tech-card"
        :class="{ 'theme-mode-switch__menu--compact': compact }"
      >
        <button
          v-for="option in THEME_OPTIONS"
          :key="option.value"
          type="button"
          class="theme-mode-switch__menu-item"
          :class="{ 'theme-mode-switch__menu-item--active': preference === option.value }"
          @click="selectOption(option.value)"
        >
          <span class="theme-mode-switch__menu-icon" aria-hidden="true">{{ option.icon }}</span>
          <span class="theme-mode-switch__menu-copy">
            <strong>{{ option.label }}</strong>
            <small>{{ option.detail }}</small>
          </span>
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.theme-mode-switch {
  position: relative;
  display: grid;
  gap: 10px;
}

.theme-mode-switch__summary {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.theme-mode-switch__eyebrow {
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.theme-mode-switch__resolved {
  font-size: 0.72rem;
  color: var(--text-secondary);
}

.theme-mode-switch__group {
  display: grid;
  gap: 8px;
}

.theme-mode-switch__group--inline {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 6px;
  padding: 4px;
  border-radius: 16px;
  border: 1px solid var(--border-color);
  background: var(--bg-surface);
}

.theme-mode-switch__option,
.theme-mode-switch__menu-item,
.theme-mode-switch__trigger {
  border: 1px solid var(--border-color);
  background: var(--bg-surface);
  color: var(--text-secondary);
  transition:
    border-color 0.24s ease,
    background 0.24s ease,
    color 0.24s ease,
    transform 0.24s var(--ease-expo);
}

.theme-mode-switch__option,
.theme-mode-switch__menu-item {
  width: 100%;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  gap: 10px;
  min-height: 44px;
  padding: 10px 12px;
  border-radius: 14px;
  text-align: left;
}

.theme-mode-switch__group--inline .theme-mode-switch__option {
  grid-template-columns: auto minmax(0, auto);
  justify-content: center;
  gap: 6px;
  min-height: 36px;
  padding: 0 10px;
  border-radius: 12px;
  border-color: transparent;
  background: transparent;
  box-shadow: none;
}

.theme-mode-switch__option:hover,
.theme-mode-switch__menu-item:hover,
.theme-mode-switch__trigger:hover {
  transform: translateY(-1px);
  border-color: var(--border-hover);
  background: var(--bg-card-hover);
  color: var(--text-primary);
}

.theme-mode-switch__option--active,
.theme-mode-switch__menu-item--active,
.theme-mode-switch__trigger--open {
  border-color: var(--border-strong);
  background: var(--state-ok-bg);
  color: var(--state-ok-text);
}

.theme-mode-switch__group--inline .theme-mode-switch__option:hover {
  border-color: transparent;
  background: var(--bg-card-hover);
}

.theme-mode-switch__option-icon,
.theme-mode-switch__menu-icon,
.theme-mode-switch__trigger-icon {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  border: 1px solid var(--border-color);
  background: rgba(255, 255, 255, 0.04);
  font-family: var(--font-seal);
  font-size: 0.72rem;
}

.theme-mode-switch__group--inline .theme-mode-switch__option-icon {
  width: 22px;
  height: 22px;
  border-radius: 8px;
  border-color: transparent;
  background: rgba(255, 255, 255, 0.06);
  font-size: 0.68rem;
}

.theme-mode-switch__option-copy,
.theme-mode-switch__menu-copy {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.theme-mode-switch__option-label {
  min-width: 0;
  font-size: 0.76rem;
  font-weight: 700;
  line-height: 1;
  white-space: nowrap;
}

.theme-mode-switch__option-copy strong,
.theme-mode-switch__menu-copy strong {
  font-size: 0.8rem;
  line-height: 1.2;
}

.theme-mode-switch__option-copy small,
.theme-mode-switch__menu-copy small {
  font-size: 0.7rem;
  line-height: 1.35;
  color: var(--text-muted);
}

.theme-mode-switch__trigger {
  min-height: 38px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 0 12px;
  border-radius: 14px;
}

.theme-mode-switch--collapsed .theme-mode-switch__trigger {
  width: 100%;
  min-height: 40px;
  padding: 0;
}

.theme-mode-switch__trigger-copy {
  font-size: 0.76rem;
  font-weight: 600;
  white-space: nowrap;
}

.theme-mode-switch__menu {
  position: absolute;
  top: calc(100% + 10px);
  right: 0;
  width: 220px;
  padding: 10px;
  border-radius: 16px;
  z-index: 12;
}

.theme-mode-switch__menu--compact {
  left: 0;
  right: auto;
}

.theme-mode-switch__menu-item + .theme-mode-switch__menu-item {
  margin-top: 8px;
}
</style>

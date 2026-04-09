<script setup>
import { computed } from 'vue'

const SECTION_ORDER = Object.freeze([
  { key: 'governance', label: '治理' },
  { key: 'analysis', label: '分析' },
  { key: 'support', label: '支持' },
])

const props = defineProps({
  collapsed: {
    type: Boolean,
    required: true,
  },
  navItems: {
    type: Array,
    required: true,
  },
  currentPath: {
    type: String,
    required: true,
  },
  workspaceLocked: {
    type: Boolean,
    required: true,
  },
})

const emit = defineEmits(['navigate'])

const navSections = computed(() =>
  SECTION_ORDER.map((section) => ({
    key: section.key,
    label: section.label,
    items: props.navItems.filter((item) => item.group === section.key),
  })).filter((section) => section.items.length > 0))

function isActive(item) {
  const prefix = item.matchPrefix || item.path
  return props.currentPath === item.path || (prefix !== '/' && props.currentPath.startsWith(prefix))
}

function itemTitle(item) {
  const summary = `${item.label} · ${item.desc}`
  if (props.workspaceLocked && item.path !== '/') {
    return `${summary}。请先完成计算卡导入。`
  }
  return summary
}
</script>

<template>
  <nav
    class="app-primary-nav-rail"
    :class="{ 'app-primary-nav-rail--collapsed': props.collapsed }"
  >
    <div class="app-primary-nav__scroll">
      <section
        v-for="section in navSections"
        :key="section.key"
        class="app-primary-nav__section"
      >
        <div v-if="!props.collapsed" class="app-primary-nav__section-title">{{ section.label }}</div>
        <div class="app-primary-nav__section-list">
          <button
            v-for="item in section.items"
            :key="item.path"
            type="button"
            class="app-primary-nav__item"
            :class="{
              'app-primary-nav__item--active': isActive(item),
              'app-primary-nav__item--collapsed': props.collapsed,
              'app-primary-nav__item--locked': props.workspaceLocked && item.path !== '/',
            }"
            :title="itemTitle(item)"
            @click="emit('navigate', item)"
          >
            <span
              class="app-primary-nav__seal"
              :class="{ 'app-primary-nav__seal--hidden': !props.collapsed }"
              aria-hidden="true"
            >
              {{ item.icon }}
            </span>
            <span
              class="app-primary-nav__body"
              :class="{ 'app-primary-nav__body--collapsed': props.collapsed }"
            >
              <strong class="app-primary-nav__label">{{ item.label }}</strong>
              <span v-if="isActive(item)" class="app-primary-nav__desc">{{ item.desc }}</span>
            </span>
          </button>
        </div>
      </section>
    </div>
  </nav>
</template>

<style scoped>
.app-primary-nav-rail {
  min-height: 0;
  min-width: 0;
  max-width: 100%;
}

.app-primary-nav-rail--collapsed {
  display: grid;
  justify-items: center;
}

.app-primary-nav__scroll {
  display: grid;
  gap: 14px;
  min-height: 0;
  overflow: visible;
  align-content: start;
  transition: gap 0.34s cubic-bezier(0.22, 1, 0.36, 1);
}

.app-primary-nav__section {
  display: grid;
  gap: 8px;
}

.app-primary-nav-rail--collapsed .app-primary-nav__scroll {
  gap: 10px;
  justify-items: center;
}

.app-primary-nav-rail--collapsed .app-primary-nav__section {
  gap: 0;
  width: 100%;
}

.app-primary-nav__section-title {
  padding: 0 2px;
  font-size: 0.64rem;
  font-weight: 600;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.app-primary-nav__section-list {
  display: grid;
  gap: 7px;
  min-width: 0;
  transition: gap 0.34s cubic-bezier(0.22, 1, 0.36, 1);
}

.app-primary-nav-rail--collapsed .app-primary-nav__section-list {
  justify-items: center;
}

.app-primary-nav__item {
  display: grid;
  grid-template-columns: 0 minmax(0, 1fr);
  gap: 0;
  align-items: center;
  width: 100%;
  max-width: 100%;
  min-height: 50px;
  padding: 9px 10px;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.02);
  color: var(--text-secondary);
  text-align: left;
  transition:
    border-color 0.24s ease,
    background 0.24s ease,
    transform 0.24s ease,
    width 0.34s cubic-bezier(0.22, 1, 0.36, 1),
    min-height 0.34s cubic-bezier(0.22, 1, 0.36, 1),
    padding 0.34s cubic-bezier(0.22, 1, 0.36, 1),
    grid-template-columns 0.34s cubic-bezier(0.22, 1, 0.36, 1);
  overflow: hidden;
}

.app-primary-nav__item--collapsed {
  grid-template-columns: 32px 0;
  justify-items: center;
  min-height: 44px;
  padding: 7px;
  width: 48px;
}

.app-primary-nav__item:hover {
  border-color: rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
  transform: translateY(-1px);
}

.app-primary-nav__item--active {
  border-color: rgba(94, 106, 210, 0.34);
  background: rgba(94, 106, 210, 0.12);
}

.app-primary-nav__item--locked {
  opacity: 0.58;
}

.app-primary-nav__seal {
  width: 32px;
  max-width: 32px;
  max-height: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.04);
  font-family: var(--font-seal);
  font-size: 0.72rem;
  overflow: hidden;
  opacity: 1;
  transform: translateX(0) scale(1);
  transition:
    max-width 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    max-height 0.22s ease,
    opacity 0.18s ease,
    transform 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.24s ease,
    background 0.24s ease,
    color 0.24s ease;
}

.app-primary-nav__seal--hidden {
  width: 0;
  max-width: 0;
  max-height: 0;
  height: 0;
  opacity: 0;
  transform: translateX(8px) scale(0.82);
  border-width: 0;
  border-color: transparent;
  background: transparent;
  font-size: 0;
}

.app-primary-nav__item--active .app-primary-nav__seal {
  border-color: rgba(94, 106, 210, 0.28);
  background: rgba(94, 106, 210, 0.18);
  color: #dbe0ff;
}

.app-primary-nav__body {
  display: grid;
  gap: 2px;
  min-width: 0;
  max-width: 180px;
  max-height: 40px;
  overflow: hidden;
  opacity: 1;
  transform: translateX(0);
  transition:
    max-width 0.34s cubic-bezier(0.22, 1, 0.36, 1),
    max-height 0.24s ease,
    opacity 0.18s ease,
    transform 0.34s cubic-bezier(0.22, 1, 0.36, 1);
}

.app-primary-nav__body--collapsed {
  max-width: 0;
  max-height: 0;
  opacity: 0;
  transform: translateX(-8px);
  pointer-events: none;
}

.app-primary-nav__label {
  font-size: 0.86rem;
  font-weight: 600;
  color: var(--text-primary);
}

.app-primary-nav__desc {
  font-size: 0.7rem;
  line-height: 1.3;
  color: var(--text-tertiary);
  white-space: normal;
  word-break: break-word;
}
</style>

<script setup>
import { computed, ref, watch } from 'vue'

const NAV_GROUPS = Object.freeze([
  { key: 'governance', label: '治理' },
  { key: 'analysis', label: '分析' },
  { key: 'support', label: '支持' },
])

const props = defineProps({
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

function resolveGroup(path) {
  const matched = props.navItems.find((item) =>
    item.path === path || (item.path !== '/' && path.startsWith(item.path)))
  return matched?.group || NAV_GROUPS[0].key
}

const activeGroup = ref(resolveGroup(props.currentPath))
const visibleItems = computed(() =>
  props.navItems.filter((item) => item.group === activeGroup.value))

watch(
  () => props.currentPath,
  (path) => {
    activeGroup.value = resolveGroup(path)
  },
)

function isActive(path) {
  return props.currentPath === path || (path !== '/' && props.currentPath.startsWith(path))
}
</script>

<template>
  <nav class="app-primary-nav-rail">
    <div class="app-primary-nav__groups">
      <button
        v-for="group in NAV_GROUPS"
        :key="group.key"
        type="button"
        class="app-primary-nav__group"
        :class="{ 'app-primary-nav__group--active': activeGroup === group.key }"
        @click="activeGroup = group.key"
      >
        {{ group.label }}
      </button>
    </div>

    <div class="app-primary-nav__scroll">
      <button
        v-for="item in visibleItems"
        :key="item.path"
        type="button"
        class="app-primary-nav__item"
        :class="{
          'app-primary-nav__item--active': isActive(item.path),
          'app-primary-nav__item--locked': props.workspaceLocked && item.path !== '/',
        }"
        :title="props.workspaceLocked && item.path !== '/' ? `请先完成计算卡导入，再打开${item.label}` : item.desc"
        @click="emit('navigate', item)"
      >
        <span class="app-primary-nav__seal">{{ item.icon }}</span>
        <span class="app-primary-nav__body">
          <strong class="app-primary-nav__label">{{ item.label }}</strong>
          <span class="app-primary-nav__desc">{{ item.desc }}</span>
        </span>
      </button>
    </div>
  </nav>
</template>

<style scoped>
.app-primary-nav-rail {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 12px;
  min-height: 0;
  overflow: hidden;
  padding: 12px;
  border-radius: 24px;
  border: 1px solid rgba(58, 95, 75, 0.08);
  background: rgba(255, 252, 247, 0.7);
}

.app-primary-nav__groups {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.app-primary-nav__group {
  border: 1px solid rgba(58, 95, 75, 0.1);
  background: rgba(255, 255, 255, 0.82);
  color: #857d74;
  border-radius: 999px;
  padding: 8px 10px;
  font-size: 0.76rem;
  line-height: 1.2;
  transition: border-color 0.24s ease, background 0.24s ease, color 0.24s ease;
}

.app-primary-nav__group--active {
  border-color: rgba(46, 139, 87, 0.18);
  background: rgba(242, 248, 244, 0.98);
  color: #2f6a46;
}

.app-primary-nav__scroll {
  display: grid;
  gap: 10px;
  min-height: 0;
  overflow-y: auto;
  padding-right: 4px;
  align-content: start;
}

.app-primary-nav__item {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr);
  gap: 10px;
  align-items: start;
  width: 100%;
  min-height: 68px;
  padding: 11px 12px 10px;
  border-radius: 16px;
  border: 1px solid rgba(58, 95, 75, 0.08);
  background: rgba(255, 252, 247, 0.76);
  color: var(--text-secondary);
  text-align: left;
  transition: border-color 0.24s ease, transform 0.24s ease, background 0.24s ease, box-shadow 0.24s ease;
}

.app-primary-nav__item:hover {
  transform: translateY(-1px);
  border-color: rgba(58, 95, 75, 0.16);
  background: rgba(255, 255, 255, 0.9);
  box-shadow: var(--shadow-card);
}

.app-primary-nav__item--active {
  border-color: rgba(46, 139, 87, 0.18);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(244, 250, 247, 0.82));
  box-shadow: 0 18px 36px rgba(46, 139, 87, 0.08);
}

.app-primary-nav__item--locked {
  opacity: 0.56;
}

.app-primary-nav__seal {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 9px;
  border: 1px solid rgba(196, 30, 58, 0.16);
  color: var(--ink-vermillion);
  background: rgba(255, 255, 255, 0.76);
  font-family: var(--font-seal);
  font-size: 0.8rem;
}

.app-primary-nav__body {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.app-primary-nav__label {
  font-size: 0.98rem;
  color: var(--text-primary);
}

.app-primary-nav__desc {
  font-size: 0.8rem;
  line-height: 1.5;
  color: var(--text-muted);
  white-space: normal;
  word-break: break-word;
}
</style>

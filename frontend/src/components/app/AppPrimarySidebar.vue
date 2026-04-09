<script setup>
import SidebarBrandCard from './SidebarBrandCard.vue'
import SidebarNavRail from './SidebarNavRail.vue'
import ThemeModeSwitch from './ThemeModeSwitch.vue'

const props = defineProps({
  appInfo: {
    type: Object,
    required: true,
  },
  collapsed: {
    type: Boolean,
    required: true,
  },
  switchServerBusy: {
    type: Boolean,
    required: true,
  },
  currentPath: {
    type: String,
    required: true,
  },
  navItems: {
    type: Array,
    required: true,
  },
  summary: {
    type: String,
    required: true,
  },
  workspaceLocked: {
    type: Boolean,
    required: true,
  },
  themePreference: {
    type: String,
    required: true,
  },
  resolvedTheme: {
    type: String,
    required: true,
  },
})

const emit = defineEmits(['navigate', 'switch-server', 'toggle-collapse', 'update:theme-preference'])
</script>

<template>
  <div
    class="app-primary-sidebar"
    :class="{ 'app-primary-sidebar--collapsed': props.collapsed }"
  >
    <SidebarBrandCard
      :app-info="props.appInfo"
      :collapsed="props.collapsed"
      :summary="props.summary"
      :switch-server-busy="props.switchServerBusy"
      @switch-server="emit('switch-server')"
    />
    <div class="app-primary-sidebar__nav">
      <SidebarNavRail
        :collapsed="props.collapsed"
        :nav-items="props.navItems"
        :current-path="props.currentPath"
        :workspace-locked="props.workspaceLocked"
        @navigate="emit('navigate', $event)"
      />
    </div>
    <div class="app-primary-sidebar__footer">
      <ThemeModeSwitch
        :theme-preference="props.themePreference"
        :preference="props.themePreference"
        :resolved-theme="props.resolvedTheme"
        :collapsed="props.collapsed"
        @update:preference="emit('update:theme-preference', $event)"
      />
      <button
        type="button"
        class="app-primary-sidebar__collapse-toggle"
        :class="{ 'app-primary-sidebar__collapse-toggle--collapsed': props.collapsed }"
        :title="props.collapsed ? '展开侧栏' : '收起侧栏'"
        :aria-label="props.collapsed ? '展开侧栏' : '收起侧栏'"
        @click="emit('toggle-collapse')"
      >
        <span
          class="app-primary-sidebar__collapse-icon"
          :class="{ 'app-primary-sidebar__collapse-icon--hidden': !props.collapsed }"
          aria-hidden="true"
        >
          展
        </span>
        <span
          class="app-primary-sidebar__collapse-label"
          :class="{ 'app-primary-sidebar__collapse-label--collapsed': props.collapsed }"
        >
          收起导航
        </span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.app-primary-sidebar {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  gap: 14px;
  min-width: 0;
  max-width: 100%;
  min-height: 100%;
  padding: 14px;
  border-radius: 28px;
  border: 1px solid var(--console-border, var(--border-color));
  background: var(--console-panel, var(--bg-card));
  overflow-x: hidden;
  box-shadow: 0 18px 44px rgba(0, 0, 0, 0.28);
  transition:
    gap 0.34s cubic-bezier(0.22, 1, 0.36, 1),
    padding 0.34s cubic-bezier(0.22, 1, 0.36, 1),
    border-radius 0.34s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.24s ease;
}

.app-primary-sidebar--collapsed {
  gap: 12px;
  padding: 12px 10px;
  border-radius: 24px;
}

.app-primary-sidebar__nav {
  min-height: 0;
  min-width: 0;
}

.app-primary-sidebar__footer {
  display: grid;
  gap: 10px;
  padding-top: 2px;
  overflow: hidden;
}

.app-primary-sidebar__collapse-toggle {
  width: 100%;
  min-height: 38px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 0 14px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: 0.75rem;
  font-weight: 600;
  line-height: 1.2;
  transition:
    border-color 0.24s ease,
    background 0.24s ease,
    color 0.24s ease,
    transform 0.24s ease,
    min-height 0.34s cubic-bezier(0.22, 1, 0.36, 1),
    padding 0.34s cubic-bezier(0.22, 1, 0.36, 1),
    gap 0.34s cubic-bezier(0.22, 1, 0.36, 1);
  overflow: hidden;
}

.app-primary-sidebar__collapse-toggle:hover {
  transform: translateY(-1px);
  border-color: var(--border-hover);
  background: var(--bg-card-hover);
  color: var(--text-primary);
}

.app-primary-sidebar__collapse-toggle--collapsed {
  padding: 0;
  min-height: 42px;
  gap: 0;
}

.app-primary-sidebar__collapse-icon {
  width: 18px;
  max-width: 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.72rem;
  overflow: hidden;
  opacity: 1;
  transform: translateX(0) scale(1);
  transition:
    max-width 0.26s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.18s ease,
    transform 0.26s cubic-bezier(0.22, 1, 0.36, 1);
}

.app-primary-sidebar__collapse-icon--hidden {
  max-width: 0;
  opacity: 0;
  transform: translateX(8px) scale(0.82);
}

.app-primary-sidebar__collapse-label {
  max-width: 92px;
  white-space: nowrap;
  overflow: hidden;
  opacity: 1;
  transform: translateX(0);
  transition:
    max-width 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.18s ease,
    transform 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}

.app-primary-sidebar__collapse-label--collapsed {
  max-width: 0;
  opacity: 0;
  transform: translateX(-8px);
}
</style>

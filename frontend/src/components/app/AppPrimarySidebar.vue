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
  isDesktop: {
    type: Boolean,
    required: true,
  },
  updateSupported: {
    type: Boolean,
    required: true,
  },
  updateBusy: {
    type: Boolean,
    required: true,
  },
  updateState: {
    type: Object,
    default: null,
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

const emit = defineEmits([
  'navigate',
  'switch-server',
  'toggle-collapse',
  'update:theme-preference',
  'check-updates',
  'open-update-target',
])

function triggerUpdateAction() {
  const hasAvailableUpdate = Boolean(props.updateState?.ok && props.updateState?.available)
  if (hasAvailableUpdate) {
    emit('open-update-target', props.updateState.downloadUrl || props.updateState.releaseUrl || '')
    return
  }
  emit('check-updates')
}
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
      <div
        v-if="props.isDesktop && props.updateSupported"
        class="app-primary-sidebar__update-card"
        :class="{ 'app-primary-sidebar__update-card--collapsed': props.collapsed }"
      >
        <div class="app-primary-sidebar__update-copy">
          <span class="app-primary-sidebar__update-kicker">桌面更新</span>
          <strong
            class="app-primary-sidebar__update-title"
            :class="{ 'app-primary-sidebar__update-title--collapsed': props.collapsed }"
          >
            {{
              props.updateState?.ok && props.updateState?.available
                ? `发现新版本 v${props.updateState.latestVersion}`
                : `当前版本 v${props.appInfo.version || '--'}`
            }}
          </strong>
          <span
            class="app-primary-sidebar__update-meta"
            :class="{ 'app-primary-sidebar__update-meta--collapsed': props.collapsed }"
          >
            {{
              props.updateState?.ok && props.updateState?.available
                ? '点击打开下载页'
                : props.updateBusy
                  ? '正在连接发布源'
                  : '手动检查桌面新版本'
            }}
          </span>
        </div>
        <button
          type="button"
          class="app-primary-sidebar__update-action"
          :class="{ 'app-primary-sidebar__update-action--accent': props.updateState?.ok && props.updateState?.available }"
          :disabled="props.updateBusy"
          :title="props.updateState?.ok && props.updateState?.available ? '打开下载地址' : '检查更新'"
          :aria-label="props.updateState?.ok && props.updateState?.available ? '打开下载地址' : '检查更新'"
          @click="triggerUpdateAction"
        >
          <span
            class="app-primary-sidebar__update-action-icon"
            aria-hidden="true"
          >
            {{ props.updateState?.ok && props.updateState?.available ? '新' : '更' }}
          </span>
          <span
            class="app-primary-sidebar__update-action-label"
            :class="{ 'app-primary-sidebar__update-action-label--collapsed': props.collapsed }"
          >
            {{
              props.updateBusy
                ? '检查中...'
                : props.updateState?.ok && props.updateState?.available
                  ? '打开下载'
                  : '检查更新'
            }}
          </span>
        </button>
      </div>
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

.app-primary-sidebar__update-card {
  display: grid;
  gap: 10px;
  padding: 12px;
  border-radius: 18px;
  border: 1px solid var(--border-color);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.035), rgba(255, 255, 255, 0.02)),
    var(--bg-surface);
  transition:
    border-color 0.24s ease,
    background 0.24s ease,
    padding 0.34s cubic-bezier(0.22, 1, 0.36, 1),
    border-radius 0.34s cubic-bezier(0.22, 1, 0.36, 1);
  overflow: hidden;
}

.app-primary-sidebar__update-card--collapsed {
  padding: 10px 8px;
  border-radius: 16px;
}

.app-primary-sidebar__update-copy {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.app-primary-sidebar__update-kicker {
  font-size: 0.64rem;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.app-primary-sidebar__update-title {
  min-width: 0;
  color: var(--text-primary);
  font-size: 0.82rem;
  font-weight: 700;
  line-height: 1.35;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  opacity: 1;
  max-height: 40px;
  transition:
    opacity 0.2s ease,
    max-height 0.28s cubic-bezier(0.22, 1, 0.36, 1),
    margin 0.28s cubic-bezier(0.22, 1, 0.36, 1);
}

.app-primary-sidebar__update-title--collapsed {
  opacity: 0;
  max-height: 0;
  margin: 0;
}

.app-primary-sidebar__update-meta {
  color: var(--text-secondary);
  font-size: 0.72rem;
  line-height: 1.4;
  opacity: 1;
  max-height: 32px;
  transition:
    opacity 0.2s ease,
    max-height 0.28s cubic-bezier(0.22, 1, 0.36, 1),
    margin 0.28s cubic-bezier(0.22, 1, 0.36, 1);
}

.app-primary-sidebar__update-meta--collapsed {
  opacity: 0;
  max-height: 0;
  margin: 0;
}

.app-primary-sidebar__update-action {
  width: 100%;
  min-height: 38px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 0 14px;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-primary);
  font-size: 0.76rem;
  font-weight: 700;
  line-height: 1.2;
  transition:
    border-color 0.24s ease,
    background 0.24s ease,
    color 0.24s ease,
    transform 0.24s ease,
    box-shadow 0.24s ease,
    padding 0.34s cubic-bezier(0.22, 1, 0.36, 1),
    gap 0.34s cubic-bezier(0.22, 1, 0.36, 1);
}

.app-primary-sidebar__update-action:hover:not(:disabled) {
  transform: translateY(-1px);
  border-color: var(--border-hover);
  background: rgba(255, 255, 255, 0.08);
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.18);
}

.app-primary-sidebar__update-action:disabled {
  cursor: progress;
  opacity: 0.78;
}

.app-primary-sidebar__update-action--accent {
  border-color: color-mix(in srgb, var(--accent-primary) 52%, rgba(255, 255, 255, 0.12));
  background: color-mix(in srgb, var(--accent-primary) 18%, rgba(255, 255, 255, 0.04));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.app-primary-sidebar__update-action--accent:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--accent-primary) 72%, rgba(255, 255, 255, 0.16));
  background: color-mix(in srgb, var(--accent-primary) 28%, rgba(255, 255, 255, 0.05));
}

.app-primary-sidebar__update-action-icon {
  width: 18px;
  max-width: 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.72rem;
  color: var(--text-secondary);
}

.app-primary-sidebar__update-action--accent .app-primary-sidebar__update-action-icon {
  color: var(--accent-primary);
}

.app-primary-sidebar__update-action-label {
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

.app-primary-sidebar__update-action-label--collapsed {
  max-width: 0;
  opacity: 0;
  transform: translateX(-8px);
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

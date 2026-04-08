<script setup>
import SidebarBrandCard from './SidebarBrandCard.vue'
import SidebarNavRail from './SidebarNavRail.vue'
import SidebarInfoDock from './SidebarInfoDock.vue'

const props = defineProps({
  appInfo: {
    type: Object,
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
  currentTime: {
    type: String,
    required: true,
  },
  telemetry: {
    type: Array,
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
})

const emit = defineEmits(['navigate', 'switch-server'])
</script>

<template>
  <div class="app-primary-sidebar">
    <SidebarBrandCard
      :app-info="props.appInfo"
      :summary="props.summary"
      :switch-server-busy="props.switchServerBusy"
      @switch-server="emit('switch-server')"
    />
    <div class="app-primary-sidebar__main">
      <SidebarNavRail
        :nav-items="props.navItems"
        :current-path="props.currentPath"
        :workspace-locked="props.workspaceLocked"
        @navigate="emit('navigate', $event)"
      />
    </div>
    <SidebarInfoDock :current-time="props.currentTime" :telemetry="props.telemetry" />
  </div>
</template>

<style scoped>
.app-primary-sidebar {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  gap: 16px;
  height: auto;
  min-height: 0;
  overflow: visible;
}

.app-primary-sidebar__main {
  min-height: 0;
  overflow: visible;
}
</style>

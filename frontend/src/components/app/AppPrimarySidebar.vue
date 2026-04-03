<script setup>
import SidebarBrandCard from './SidebarBrandCard.vue'
import SidebarNavRail from './SidebarNavRail.vue'
import SidebarInfoDock from './SidebarInfoDock.vue'

const props = defineProps({
  appInfo: {
    type: Object,
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

const emit = defineEmits(['navigate'])
</script>

<template>
  <div class="app-primary-sidebar">
    <SidebarBrandCard
      :app-info="props.appInfo"
      :summary="props.summary"
    />
    <div class="app-primary-sidebar__main">
      <SidebarNavRail
        :nav-items="props.navItems"
        :current-path="props.currentPath"
        :workspace-locked="props.workspaceLocked"
        @navigate="emit('navigate', $event)"
      />
    </div>
    <SidebarInfoDock :current-time="props.currentTime" />
  </div>
</template>

<style scoped>
.app-primary-sidebar {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  gap: 16px;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.app-primary-sidebar__main {
  min-height: 0;
  overflow: hidden;
}
</style>

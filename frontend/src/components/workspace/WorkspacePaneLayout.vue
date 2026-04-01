<template>
  <div class="workspace-pane-layout">
    <div class="workspace-pane-layout__main">
      <slot name="main" />
    </div>
    <aside class="workspace-pane-layout__side">
      <slot name="side" />
    </aside>
  </div>
</template>

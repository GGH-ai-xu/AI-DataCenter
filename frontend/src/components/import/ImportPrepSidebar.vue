<script setup>
const props = defineProps({
  title: { type: String, required: true },
  description: { type: String, required: true },
  connectionSummary: { type: String, required: true },
  selectedSummary: { type: String, required: true },
  scopeSummary: { type: String, required: true },
  note: { type: String, required: true },
})
</script>

<template>
  <aside class="tech-card import-prep-sidebar">
    <div class="import-prep-sidebar__brand">
      <img class="import-prep-sidebar__logo" src="/logo.svg" alt="AI-DataCenter logo" />
      <div class="import-prep-sidebar__brand-copy">
        <div class="import-prep-sidebar__eyebrow">GPU GOVERNANCE CONSOLE</div>
        <h1 class="import-prep-sidebar__title">{{ props.title }}</h1>
      </div>
    </div>

    <p class="import-prep-sidebar__description">{{ props.description }}</p>

    <div class="import-prep-sidebar__facts">
      <article class="import-prep-sidebar__fact">
        <span>当前连接</span>
        <strong>{{ props.connectionSummary }}</strong>
      </article>
      <article class="import-prep-sidebar__fact">
        <span>本次选择</span>
        <strong>{{ props.selectedSummary }}</strong>
      </article>
      <article class="import-prep-sidebar__fact">
        <span>控制范围</span>
        <strong>{{ props.scopeSummary }}</strong>
      </article>
    </div>

    <p class="import-prep-sidebar__note">{{ props.note }}</p>
  </aside>
</template>

<style scoped>
.import-prep-sidebar {
  position: sticky;
  top: 24px;
  align-self: start;
  display: grid;
  gap: 18px;
  padding: 24px;
  max-height: calc(100vh - 48px);
}

.import-prep-sidebar__brand {
  display: flex;
  align-items: flex-start;
  gap: 14px;
}

.import-prep-sidebar__logo {
  width: 58px;
  height: 58px;
  border-radius: 16px;
  flex-shrink: 0;
  filter: drop-shadow(0 12px 24px rgba(46, 139, 87, 0.14));
}

.import-prep-sidebar__brand-copy {
  min-width: 0;
}

.import-prep-sidebar__eyebrow,
.import-prep-sidebar__fact span,
.import-prep-sidebar__note {
  font-size: 0.76rem;
  line-height: 1.7;
  letter-spacing: 0.08em;
  color: var(--text-muted);
}

.import-prep-sidebar__title {
  margin-top: 6px;
  font-family: var(--font-xingshu);
  font-size: clamp(2rem, 3vw, 3rem);
  font-weight: 400;
  line-height: 1.08;
  color: var(--text-primary);
}

.import-prep-sidebar__description {
  font-size: 0.95rem;
  line-height: 1.85;
  color: var(--text-secondary);
}

.import-prep-sidebar__facts {
  display: grid;
  gap: 12px;
}

.import-prep-sidebar__fact {
  display: grid;
  gap: 8px;
  padding: 16px;
  border-radius: 20px;
  border: 1px solid rgba(26, 26, 26, 0.05);
  background: rgba(255, 252, 247, 0.72);
}

.import-prep-sidebar__fact strong {
  font-size: 0.98rem;
  line-height: 1.65;
  color: var(--text-primary);
  word-break: break-word;
}

.import-prep-sidebar__note {
  padding-left: 14px;
  border-left: 2px solid rgba(46, 139, 87, 0.18);
  letter-spacing: 0.04em;
}

@media (max-width: 1080px) {
  .import-prep-sidebar {
    position: static;
    max-height: none;
  }
}
</style>

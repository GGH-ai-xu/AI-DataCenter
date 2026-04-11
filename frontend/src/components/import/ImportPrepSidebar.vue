<script setup>
const props = defineProps({
  title: { type: String, required: true },
  description: { type: String, required: true },
  steps: { type: Array, required: true },
  note: { type: String, required: true },
})
</script>

<template>
  <aside class="tech-card import-prep-sidebar">
    <div class="import-prep-sidebar__brand">
      <img class="import-prep-sidebar__logo" src="/logo.svg" alt="AI-DataCenter logo" />
      <div class="import-prep-sidebar__eyebrow">智算中心优化代码生成系统</div>
    </div>

    <div class="import-prep-sidebar__brand-copy">
      <h1 class="import-prep-sidebar__title">{{ props.title }}</h1>
      <p class="import-prep-sidebar__description">{{ props.description }}</p>
    </div>

    <section class="import-prep-sidebar__steps">
      <div class="import-prep-sidebar__section-label">步骤引导</div>
      <article
        v-for="step in props.steps"
        :key="step.key"
        class="import-prep-sidebar__step"
        :class="{
          'import-prep-sidebar__step--current': step.state === 'current',
          'import-prep-sidebar__step--done': step.state === 'done' || step.state === 'ready',
        }"
      >
        <div class="import-prep-sidebar__step-index">{{ String(step.order).padStart(2, '0') }}</div>
        <div class="import-prep-sidebar__step-copy">
          <div class="import-prep-sidebar__step-title">{{ step.label }}</div>
          <div class="import-prep-sidebar__step-desc">{{ step.desc }}</div>
        </div>
        <span class="import-prep-sidebar__step-state">
          {{ step.state === 'current' ? '当前' : (step.state === 'done' || step.state === 'ready' ? '已就绪' : '待完成') }}
        </span>
      </article>
    </section>

    <section class="import-prep-sidebar__note">
      <div class="import-prep-sidebar__section-label">导入规则</div>
      <p>{{ props.note }}</p>
    </section>
  </aside>
</template>

<style scoped>
.import-prep-sidebar {
  position: sticky;
  top: 24px;
  align-self: start;
  display: grid;
  gap: 22px;
  padding: 24px;
  max-height: calc(100vh - 48px);
  overflow: auto;
}

.import-prep-sidebar__brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.import-prep-sidebar__logo {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  flex-shrink: 0;
  box-shadow: none;
}

.import-prep-sidebar__brand-copy {
  display: grid;
  gap: 10px;
}

.import-prep-sidebar__title {
  font-family: var(--font-ui);
  font-size: clamp(1.4rem, 2vw, 1.8rem);
  font-weight: 600;
  line-height: 1.08;
  letter-spacing: -0.03em;
  color: var(--import-text, var(--text-primary));
}

.import-prep-sidebar__description {
  font-size: 0.9rem;
  line-height: 1.8;
  color: var(--import-text-secondary, var(--text-secondary));
}

.import-prep-sidebar__eyebrow,
.import-prep-sidebar__section-label,
.import-prep-sidebar__step-state {
  font-family: var(--font-ui);
  font-size: 0.72rem;
  line-height: 1.5;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--import-text-muted, var(--text-muted));
}

.import-prep-sidebar__steps {
  display: grid;
  gap: 12px;
}

.import-prep-sidebar__step {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: start;
  gap: 12px;
  padding: 14px 14px 14px 12px;
  border-radius: 16px;
  border: 1px solid var(--import-border, rgba(255, 255, 255, 0.08));
  background: var(--import-surface-soft, rgba(255, 255, 255, 0.03));
}

.import-prep-sidebar__step--current {
  border-color: var(--import-border-strong, rgba(94, 106, 210, 0.32));
  background: var(--import-accent-soft, rgba(94, 106, 210, 0.12));
}

.import-prep-sidebar__step--done {
  border-color: rgba(255, 255, 255, 0.1);
}

.import-prep-sidebar__step-index {
  width: 30px;
  min-width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  border: 1px solid var(--import-border, rgba(255, 255, 255, 0.08));
  background: var(--import-surface-bg, rgba(255, 255, 255, 0.04));
  color: var(--import-text, var(--text-primary));
  font-family: var(--font-seal);
  font-size: 0.76rem;
}

.import-prep-sidebar__step-copy {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.import-prep-sidebar__step-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--import-text, var(--text-primary));
}

.import-prep-sidebar__step-desc {
  font-size: 0.78rem;
  line-height: 1.7;
  color: var(--import-text-muted, var(--text-muted));
}

.import-prep-sidebar__step-state {
  align-self: center;
  letter-spacing: 0.08em;
}

.import-prep-sidebar__note {
  display: grid;
  gap: 8px;
  padding: 16px 18px;
  border-radius: 16px;
  border: 1px solid var(--import-border, rgba(255, 255, 255, 0.08));
  background: var(--import-surface-soft, rgba(255, 255, 255, 0.03));
}

.import-prep-sidebar__note p {
  font-size: 0.8rem;
  line-height: 1.8;
  color: var(--import-text-secondary, var(--text-secondary));
}

@media (max-width: 1080px) {
  .import-prep-sidebar {
    position: static;
    max-height: none;
  }
}
</style>

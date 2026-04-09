<script setup>
import UserRuleCard from './UserRuleCard.vue'

const props = defineProps({
  users: { type: Array, default: () => [] },
})

const emit = defineEmits(['save', 'reset'])
</script>

<template>
  <section v-if="props.users.length" class="tech-card rules-panel">
    <div class="rules-panel__head">
      <div class="panel-card__title">用户额度规则</div>
      <div class="rules-panel__hint">这里仅保留做策略判断所需的最小上下文，公平占比与倾斜解释统一留在公平诊断页。</div>
    </div>

    <div class="rules-grid">
      <UserRuleCard
        v-for="user in props.users"
        :key="user.username"
        :user="user"
        @save="emit('save', $event)"
        @reset="emit('reset', $event)"
      />
    </div>
  </section>

  <section v-else class="tech-card rules-panel rules-panel--empty">
    <div class="panel-card__title">用户额度规则</div>
    <div class="panel-card__item">当前没有活跃用户需要配置规则。</div>
  </section>
</template>

<style scoped>
.rules-panel { padding: 18px; margin-bottom: 14px; }
.rules-panel__head { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 4px; }
.rules-panel__hint { font-size: 0.75rem; line-height: 1.6; color: var(--text-muted); }
.rules-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-top: 12px; }
@media (max-width: 1400px) { .rules-grid { grid-template-columns: 1fr; } }
</style>

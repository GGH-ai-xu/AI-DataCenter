<script setup>
const props = defineProps({
  hosts: { type: Array, required: true },
  loading: { type: Boolean, required: true },
  errorText: { type: String, required: true },
  scope: { type: String, required: true },
  canViewAll: { type: Boolean, required: true },
  activeHostId: { type: Number, default: null },
  deletingHostId: { type: Number, default: null },
})

const emit = defineEmits(['update:scope', 'refresh', 'edit', 'scan', 'delete'])

function providerLabel(providerType) {
  if (providerType === 'ssh_linux') return 'SSH Linux'
  if (providerType === 'http_remote') return '远程 Agent'
  return '本机 Agent'
}

function targetSummary(host) {
  if (host.agent_url) return host.agent_url
  return `${host.username || 'user'}@${host.host || 'host'}:${host.port || 22}`
}

function scanActionLabel(host) {
  return host.credential_status === 'unreadable' ? '补录凭据' : '直接扫描'
}

function credentialNotice(host) {
  if (host.credential_status === 'unreadable') {
    return host.credential_error || '已保存 SSH 凭据失效，需要重新录入密码或私钥。'
  }
  if (host.credential_status === 'missing' && host.provider_type === 'ssh_linux') {
    return '这条 SSH 主机当前没有可复用凭据，需要重新录入密码或私钥。'
  }
  return ''
}

function formatTime(value) {
  if (!value) return '暂无记录'
  return new Date(Number(value) * 1000).toLocaleString('zh-CN', {
    hour12: false,
  })
}
</script>

<template>
  <section class="saved-host-stage">
    <header class="saved-host-stage__header">
      <div>
        <h2>已保存主机</h2>
        <p>先复用成功连接过的目标，再决定是否需要新建连接。</p>
      </div>
      <div class="saved-host-stage__controls">
        <div class="saved-host-stage__scope">
          <button
            type="button"
            class="saved-host-stage__scope-button"
            :class="{ 'saved-host-stage__scope-button--active': props.scope === 'mine' }"
            @click="emit('update:scope', 'mine')"
          >
            我的主机
          </button>
          <button
            v-if="props.canViewAll"
            type="button"
            class="saved-host-stage__scope-button"
            :class="{ 'saved-host-stage__scope-button--active': props.scope === 'all' }"
            @click="emit('update:scope', 'all')"
          >
            全部主机
          </button>
        </div>
        <button type="button" class="btn-tech" @click="emit('refresh')">
          刷新列表
        </button>
      </div>
    </header>

    <p v-if="props.errorText" class="saved-host-stage__error">{{ props.errorText }}</p>
    <div v-if="props.loading" class="saved-host-stage__empty">正在读取已保存主机...</div>
    <div v-else-if="props.hosts.length <= 0" class="saved-host-stage__empty">
      还没有可复用的主机记录。你可以切换到“连接来源”阶段手动新建连接，首次导入成功后这里会自动出现记录。
    </div>

    <div v-else class="saved-host-stage__grid">
      <article
        v-for="host in props.hosts"
        :key="host.id"
        class="saved-host-card"
        :class="{ 'saved-host-card--active': props.activeHostId === host.id }"
      >
        <div class="saved-host-card__head">
          <div>
            <h3>{{ host.label }}</h3>
            <p>{{ targetSummary(host) }}</p>
          </div>
          <span class="saved-host-card__badge">{{ providerLabel(host.provider_type) }}</span>
        </div>
        <dl class="saved-host-card__meta">
          <div>
            <dt>认证方式</dt>
            <dd>{{ host.auth_type || '自动复用' }}</dd>
          </div>
          <div>
            <dt>最近连接</dt>
            <dd>{{ formatTime(host.last_connected_at) }}</dd>
          </div>
          <div v-if="props.scope === 'all' && host.owner_username">
            <dt>归属用户</dt>
            <dd>{{ host.owner_username }}</dd>
          </div>
        </dl>
        <p v-if="credentialNotice(host)" class="saved-host-card__warning">{{ credentialNotice(host) }}</p>
        <div class="saved-host-card__actions">
          <button type="button" class="btn-tech" @click="emit('edit', host.id)">
            编辑连接
          </button>
          <button type="button" class="btn-tech btn-tech--primary" @click="emit('scan', host.id)">
            {{ scanActionLabel(host) }}
          </button>
          <button
            type="button"
            class="btn-tech"
            :disabled="props.deletingHostId === host.id"
            @click="emit('delete', host.id)"
          >
            {{ props.deletingHostId === host.id ? '删除中...' : '删除记录' }}
          </button>
        </div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.saved-host-stage {
  display: grid;
  gap: 18px;
}

.saved-host-stage__header {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 16px;
}

.saved-host-stage__header p,
.saved-host-stage__empty,
.saved-host-stage__error {
  color: var(--text-muted);
  line-height: 1.7;
}

.saved-host-stage__controls,
.saved-host-stage__scope {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.saved-host-stage__scope-button {
  min-height: 40px;
  padding: 0 14px;
  border-radius: 999px;
  border: 1px solid rgba(58, 95, 75, 0.12);
  background: rgba(255, 255, 255, 0.86);
}

.saved-host-stage__scope-button--active {
  border-color: rgba(46, 139, 87, 0.2);
  background: rgba(242, 248, 244, 0.96);
  color: #2f6a46;
}

.saved-host-stage__grid {
  display: grid;
  gap: 14px;
}

.saved-host-card {
  padding: 18px;
  border-radius: 22px;
  border: 1px solid rgba(58, 95, 75, 0.12);
  background: rgba(255, 252, 247, 0.94);
  display: grid;
  gap: 16px;
}

.saved-host-card--active {
  border-color: rgba(30, 92, 77, 0.26);
  box-shadow: 0 14px 28px rgba(30, 92, 77, 0.08);
}

.saved-host-card__head,
.saved-host-card__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 12px;
}

.saved-host-card__head h3,
.saved-host-card__meta dd {
  word-break: break-word;
}

.saved-host-card__head p,
.saved-host-card__meta dt,
.saved-host-card__warning {
  color: var(--text-muted);
}

.saved-host-card__warning {
  margin: 0;
  color: #a14a3f;
  line-height: 1.6;
}

.saved-host-card__badge {
  align-self: flex-start;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(242, 248, 244, 0.96);
  color: #2f6a46;
}

.saved-host-card__meta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.saved-host-card__meta div {
  display: grid;
  gap: 4px;
}
</style>

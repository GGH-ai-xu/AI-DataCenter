<script setup>
import { computed } from 'vue'
import ImportSourcePanel from './ImportSourcePanel.vue'
const SOURCE_MODES = Object.freeze([
  { key: 'http_local', label: '本机 Agent' },
  { key: 'http_remote', label: '远程 Agent' },
  { key: 'ssh_linux', label: 'SSH Linux' },
])

const props = defineProps({
  providerType: { type: String, required: true },
  agentUrl: { type: String, default: '' },
  agentLabel: { type: String, default: '' },
  host: { type: String, default: '' },
  port: { type: Number, default: 22 },
  username: { type: String, default: '' },
  authType: { type: String, default: 'password' },
  password: { type: String, default: '' },
  privateKey: { type: String, default: '' },
  privateKeyPassphrase: { type: String, default: '' },
  sudoEnabled: { type: Boolean, default: false },
  sudoPassword: { type: String, default: '' },
  scanBusy: { type: Boolean, required: true },
  feedback: { type: Object, default: null },
  connectionSummary: { type: String, required: true },
  hostFingerprint: { type: String, default: '' },
})

const emit = defineEmits([
  'update:providerType',
  'update:agentUrl',
  'update:agentLabel',
  'update:host',
  'update:port',
  'update:username',
  'update:authType',
  'update:password',
  'update:privateKey',
  'update:privateKeyPassphrase',
  'update:sudoEnabled',
  'update:sudoPassword',
  'scan',
])

const authLabel = computed(() => (props.providerType === 'ssh_linux'
  ? (props.authType === 'private_key' ? '私钥认证' : '密码认证')
  : 'Agent 直连'))

const targetAddress = computed(() => {
  if (props.providerType === 'ssh_linux') {
    const host = props.host || '主机待输入'
    const user = props.username || '用户待输入'
    return `ssh://${user}@${host}:${props.port || 22}`
  }
  if (props.providerType === 'http_remote') {
    return props.agentUrl || '远程地址待输入'
  }
  return '本机 Agent / 回环连接'
})

const scanState = computed(() => {
  if (props.scanBusy) return '正在扫描'
  if (props.feedback?.tone === 'ok') return '最近扫描成功'
  if (props.feedback?.tone === 'error') return '最近扫描失败'
  return '等待扫描'
})

const connectionFacts = computed(() => {
  const facts = [
    { label: '当前目标', value: targetAddress.value },
    { label: '认证方式', value: authLabel.value },
    { label: '连接标签', value: props.agentLabel || '待填写' },
    { label: '最近状态', value: scanState.value },
  ]
  if (props.hostFingerprint) {
    facts.push({ label: '主机指纹', value: props.hostFingerprint })
  }
  return facts
})
</script>
<template>
  <section class="import-connection-stage">
    <div class="import-connection-stage__shell">
      <div class="import-connection-stage__main">
        <section class="tech-card import-connection-stage__modes">
          <div class="section-title">连接来源</div>
          <div class="import-connection-stage__mode-strip">
            <button
              v-for="mode in SOURCE_MODES"
              :key="mode.key"
              type="button"
              class="import-connection-stage__mode"
              :class="{ 'import-connection-stage__mode--active': props.providerType === mode.key }"
              :disabled="props.scanBusy"
              @click="emit('update:providerType', mode.key)"
            >
              {{ mode.label }}
            </button>
          </div>
        </section>
        <ImportSourcePanel
          :provider-type="props.providerType"
          :agent-url="props.agentUrl"
          :agent-label="props.agentLabel"
          :host="props.host"
          :port="props.port"
          :username="props.username"
          :auth-type="props.authType"
          :password="props.password"
          :private-key="props.privateKey"
          :private-key-passphrase="props.privateKeyPassphrase"
          :sudo-enabled="props.sudoEnabled"
          :sudo-password="props.sudoPassword"
          :busy="props.scanBusy"
          @update:provider-type="emit('update:providerType', $event)"
          @update:agent-url="emit('update:agentUrl', $event)"
          @update:agent-label="emit('update:agentLabel', $event)"
          @update:host="emit('update:host', $event)"
          @update:port="emit('update:port', $event)"
          @update:username="emit('update:username', $event)"
          @update:auth-type="emit('update:authType', $event)"
          @update:password="emit('update:password', $event)"
          @update:private-key="emit('update:privateKey', $event)"
          @update:private-key-passphrase="emit('update:privateKeyPassphrase', $event)"
          @update:sudo-enabled="emit('update:sudoEnabled', $event)"
          @update:sudo-password="emit('update:sudoPassword', $event)"
        />
        <section class="tech-card import-connection-stage__action-card">
          <div class="import-connection-stage__action-head">
            <div>
              <div class="section-title">连接与扫描</div>
              <p class="import-connection-stage__action-copy">
                先确认连接信息，再发起一次真实扫描，后续验机和选卡都以这次结果为准。
              </p>
            </div>
            <span class="status-badge" :class="props.feedback?.tone === 'ok' ? 'status-badge--ok' : 'status-badge--warning'">
              {{ scanState }}
            </span>
          </div>

          <div class="import-connection-stage__action-row">
            <button
              type="button"
              class="btn-tech btn-tech--primary"
              :disabled="props.scanBusy"
              @click="emit('scan')"
            >
              {{ props.scanBusy ? '扫描中...' : '扫描硬件' }}
            </button>
            <div class="import-connection-stage__action-summary">{{ props.connectionSummary }}</div>
          </div>

          <div
            v-if="props.feedback"
            class="import-connection-stage__feedback"
            :class="`import-connection-stage__feedback--${props.feedback.tone}`"
          >
            {{ props.feedback.text }}
          </div>
        </section>
      </div>

      <aside class="tech-card import-connection-stage__aside">
        <div class="section-title">连接摘要</div>
        <div class="import-connection-stage__facts">
          <article
            v-for="fact in connectionFacts"
            :key="fact.label"
            class="import-connection-stage__fact"
          >
            <span>{{ fact.label }}</span>
            <strong>{{ fact.value }}</strong>
          </article>
        </div>
      </aside>
    </div>
  </section>
</template>
<style scoped>
.import-connection-stage,
.import-connection-stage__main {
  display: grid;
  gap: 16px;
  min-height: 0;
}

.import-connection-stage__shell {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(240px, 0.8fr);
  gap: 16px;
  min-height: 0;
}

.import-connection-stage__modes,
.import-connection-stage__action-card,
.import-connection-stage__aside {
  display: grid;
  gap: 14px;
  padding: 20px;
}

.import-connection-stage__mode-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.import-connection-stage__mode {
  min-height: 44px;
  border-radius: 16px;
  border: 1px solid rgba(58, 95, 75, 0.12);
  background: rgba(255, 252, 247, 0.82);
  color: var(--text-secondary);
}

.import-connection-stage__mode--active {
  border-color: rgba(46, 139, 87, 0.18);
  background: rgba(244, 250, 247, 0.88);
  color: var(--text-primary);
}

.import-connection-stage__action-head,
.import-connection-stage__action-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
}

.import-connection-stage__action-copy,
.import-connection-stage__action-summary,
.import-connection-stage__fact span {
  font-size: 0.78rem;
  line-height: 1.7;
  color: var(--text-muted);
}

.import-connection-stage__action-summary {
  max-width: 100%;
  word-break: break-word;
}

.import-connection-stage__feedback {
  padding: 12px 14px;
  border-radius: 16px;
  font-size: 0.82rem;
  line-height: 1.7;
}

.import-connection-stage__feedback--ok {
  color: #2f6a46;
  background: rgba(46, 139, 87, 0.08);
}

.import-connection-stage__feedback--warning {
  color: #8a6510;
  background: rgba(212, 175, 55, 0.12);
}

.import-connection-stage__feedback--error {
  color: #9a1730;
  background: rgba(196, 30, 58, 0.08);
}

.import-connection-stage__facts {
  display: grid;
  gap: 12px;
}

.import-connection-stage__fact {
  display: grid;
  gap: 6px;
  padding: 14px;
  border-radius: 18px;
  background: rgba(255, 252, 247, 0.72);
  border: 1px solid rgba(26, 26, 26, 0.05);
}

.import-connection-stage__fact strong {
  font-size: 0.94rem;
  line-height: 1.6;
  color: var(--text-primary);
  word-break: break-word;
}

@media (max-width: 960px) {
  .import-connection-stage__shell {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .import-connection-stage__mode-strip {
    grid-template-columns: 1fr;
  }
}
</style>

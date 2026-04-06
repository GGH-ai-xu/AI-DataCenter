<script setup>
import { computed } from 'vue'

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
  busy: { type: Boolean, default: false },
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
])

const isSsh = computed(() => props.providerType === 'ssh_linux')
const isHttpRemote = computed(() => props.providerType === 'http_remote')
</script>

<template>
  <section class="tech-card import-source-panel">
    <div class="section-title">连接表单</div>

    <label class="import-source-panel__field">
      <span>导入标签</span>
      <input
        :value="props.agentLabel"
        type="text"
        maxlength="120"
        :disabled="props.busy"
        placeholder="例如：实验室 A / 本机 Agent"
        @input="emit('update:agentLabel', $event.target.value)"
      >
    </label>

    <label v-if="isHttpRemote" class="import-source-panel__field">
      <span>远程 Agent 地址</span>
      <input
        :value="props.agentUrl"
        type="text"
        maxlength="300"
        :disabled="props.busy"
        placeholder="http://10.0.0.8:8001"
        @input="emit('update:agentUrl', $event.target.value)"
      >
    </label>

    <template v-if="isSsh">
      <div class="import-source-panel__grid">
        <label class="import-source-panel__field">
          <span>主机地址</span>
          <input
            :value="props.host"
            type="text"
            maxlength="255"
            :disabled="props.busy"
            placeholder="10.0.0.8"
            @input="emit('update:host', $event.target.value)"
          >
        </label>

        <label class="import-source-panel__field">
          <span>端口</span>
          <input
            :value="props.port"
            type="number"
            min="1"
            max="65535"
            :disabled="props.busy"
            @input="emit('update:port', Number($event.target.value || 22))"
          >
        </label>
      </div>

      <label class="import-source-panel__field">
        <span>用户名</span>
        <input
          :value="props.username"
          type="text"
          maxlength="120"
          :disabled="props.busy"
          placeholder="gpuops"
          @input="emit('update:username', $event.target.value)"
        >
      </label>

      <div class="import-source-panel__auth-toggle">
        <button
          type="button"
          class="import-source-panel__auth-button"
          :class="{ 'import-source-panel__auth-button--active': props.authType === 'password' }"
          :disabled="props.busy"
          @click="emit('update:authType', 'password')"
        >
          密码认证
        </button>
        <button
          type="button"
          class="import-source-panel__auth-button"
          :class="{ 'import-source-panel__auth-button--active': props.authType === 'private_key' }"
          :disabled="props.busy"
          @click="emit('update:authType', 'private_key')"
        >
          私钥认证
        </button>
      </div>

      <label v-if="props.authType === 'password'" class="import-source-panel__field">
        <span>SSH 密码</span>
        <input
          :value="props.password"
          type="password"
          maxlength="5000"
          :disabled="props.busy"
          placeholder="输入 SSH 密码"
          @input="emit('update:password', $event.target.value)"
        >
      </label>

      <template v-else>
        <label class="import-source-panel__field">
          <span>私钥</span>
          <textarea
            :value="props.privateKey"
            rows="5"
            :disabled="props.busy"
            placeholder="-----BEGIN OPENSSH PRIVATE KEY-----"
            @input="emit('update:privateKey', $event.target.value)"
          ></textarea>
        </label>

        <label class="import-source-panel__field">
          <span>私钥口令</span>
          <input
            :value="props.privateKeyPassphrase"
            type="password"
            maxlength="5000"
            :disabled="props.busy"
            placeholder="如私钥未加密可留空"
            @input="emit('update:privateKeyPassphrase', $event.target.value)"
          >
        </label>
      </template>

      <label class="import-source-panel__checkbox">
        <input
          :checked="props.sudoEnabled"
          type="checkbox"
          :disabled="props.busy"
          @change="emit('update:sudoEnabled', $event.target.checked)"
        >
        <span>启用 sudo 治理动作</span>
      </label>

      <label v-if="props.sudoEnabled" class="import-source-panel__field">
        <span>sudo 密码</span>
        <input
          :value="props.sudoPassword"
          type="password"
          maxlength="5000"
          :disabled="props.busy"
          placeholder="如已配置免密 sudo 可留空"
          @input="emit('update:sudoPassword', $event.target.value)"
        >
      </label>
    </template>
  </section>
</template>

<style scoped>
.import-source-panel {
  display: grid;
  gap: 16px;
  padding: 20px;
}

.import-source-panel__field {
  display: grid;
  gap: 8px;
}

.import-source-panel__field span {
  font-size: 0.76rem;
  color: var(--text-muted);
}

.import-source-panel__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.import-source-panel__auth-toggle {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.import-source-panel__auth-button {
  min-height: 44px;
  border-radius: 16px;
  border: 1px solid rgba(58, 95, 75, 0.12);
  background: rgba(255, 252, 247, 0.82);
  color: var(--text-secondary);
}

.import-source-panel__auth-button--active {
  border-color: rgba(46, 139, 87, 0.18);
  background: rgba(244, 250, 247, 0.88);
  color: var(--text-primary);
}

.import-source-panel__checkbox {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 0.82rem;
  color: var(--text-secondary);
}

.import-source-panel textarea {
  min-height: 140px;
  resize: vertical;
}

@media (max-width: 720px) {
  .import-source-panel__grid,
  .import-source-panel__auth-toggle {
    grid-template-columns: 1fr;
  }
}
</style>

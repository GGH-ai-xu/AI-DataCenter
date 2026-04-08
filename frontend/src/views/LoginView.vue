<script setup>
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth.js'


const router = useRouter()
const auth = useAuthStore()
const form = reactive({
  username: '',
  password: '',
})
const busy = ref(false)
const errorText = ref('')
const canSubmit = computed(() => form.username.trim() && form.password)

async function handleSubmit() {
  if (!canSubmit.value) return
  busy.value = true
  errorText.value = ''
  try {
    const user = await auth.login({
      username: form.username.trim(),
      password: form.password,
    })
    await router.replace(user?.must_change_password ? '/change-password' : '/import')
  } catch (error) {
    errorText.value = error?.response?.data?.detail || error?.message || '登录失败'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <section class="auth-shell">
      <article class="auth-hero tech-card">
        <div class="auth-hero__eyebrow">GPU Governance Console</div>
        <h1 class="auth-hero__title">把 GPU 治理台做成真正的产品界面，而不是拼起来的后台页。</h1>
        <p class="auth-hero__description">
          登录后先进入导入层，确定本次要治理的机器与计算卡范围。后续所有告警、调度、观察与复盘都会围绕这一组 GPU 展开。
        </p>
        <div class="auth-hero__grid">
          <article class="auth-hero__item">
            <span>导入范围</span>
            <strong>先选机器，再进控制台</strong>
          </article>
          <article class="auth-hero__item">
            <span>实时链路</span>
            <strong>单一工作区持续观察</strong>
          </article>
          <article class="auth-hero__item">
            <span>治理体验</span>
            <strong>预算、告警、任务统一收口</strong>
          </article>
        </div>
      </article>

      <section class="auth-card tech-card">
        <div class="auth-card__eyebrow">平台登录</div>
        <h1 class="auth-card__title">进入 GPU 治理控制台</h1>
        <p class="auth-card__description">
          先完成平台账号认证，再进入导入层选择本次受管机器与计算卡范围。
        </p>
        <form class="auth-form" @submit.prevent="handleSubmit">
          <label class="auth-form__field">
            <span>用户名</span>
            <input v-model="form.username" type="text" autocomplete="username" placeholder="例如：admin" />
          </label>
          <label class="auth-form__field">
            <span>密码</span>
            <input v-model="form.password" type="password" autocomplete="current-password" placeholder="输入平台密码" />
          </label>
          <p v-if="errorText" class="auth-form__error">{{ errorText }}</p>
          <button type="submit" class="btn-tech btn-tech--primary auth-form__submit" :disabled="busy || !canSubmit">
            {{ busy ? '登录中...' : '登录并进入导入层' }}
          </button>
        </form>
        <p class="auth-card__note">
          首次启动默认管理员账号固定为 `admin`，默认密码为 `admin123456`，可直接进入导入层。
        </p>
      </section>
    </section>
  </div>
</template>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
}

.auth-shell {
  width: min(1160px, 100%);
  display: grid;
  grid-template-columns: minmax(0, 1.12fr) minmax(360px, 420px);
  gap: 22px;
  align-items: stretch;
}

.auth-hero,
.auth-card {
  padding: 28px;
}

.auth-hero {
  display: grid;
  gap: 18px;
  align-content: start;
}

.auth-hero__eyebrow,
.auth-card__eyebrow {
  font-family: var(--font-seal);
  font-size: 0.72rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.auth-hero__title {
  font-size: clamp(2.2rem, 4vw, 3.8rem);
  line-height: 0.98;
  font-weight: 600;
  letter-spacing: -0.05em;
  background: linear-gradient(180deg, #ffffff 0%, rgba(237, 238, 247, 0.72) 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.auth-hero__description,
.auth-card__description,
.auth-card__note {
  color: var(--text-secondary);
  line-height: 1.8;
}

.auth-hero__grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.auth-hero__item {
  display: grid;
  gap: 6px;
  padding: 16px;
  border-radius: 18px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.065), rgba(255, 255, 255, 0.03));
}

.auth-hero__item span {
  font-size: 0.72rem;
  color: var(--text-muted);
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.auth-hero__item strong {
  font-size: 0.96rem;
  line-height: 1.5;
  color: var(--text-primary);
}

.auth-card {
  display: grid;
  gap: 16px;
  align-content: start;
}

.auth-card__title {
  font-family: var(--font-ui);
  font-size: 1.86rem;
  line-height: 1.06;
  letter-spacing: -0.04em;
}

.auth-form {
  display: grid;
  gap: 16px;
}

.auth-form__field {
  display: grid;
  gap: 8px;
}

.auth-form__field span {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-tertiary);
}

.auth-form__error {
  color: var(--accent-danger);
  font-size: 0.82rem;
  line-height: 1.6;
}

.auth-form__submit {
  margin-top: 4px;
}

@media (max-width: 960px) {
  .auth-shell {
    grid-template-columns: 1fr;
  }

  .auth-hero__grid {
    grid-template-columns: 1fr;
  }
}
</style>

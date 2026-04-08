<script setup>
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth.js'


const router = useRouter()
const auth = useAuthStore()
const form = reactive({
  currentPassword: '',
  newPassword: '',
  confirmPassword: '',
})
const busy = ref(false)
const errorText = ref('')
const passwordMismatch = computed(() => form.confirmPassword && form.newPassword !== form.confirmPassword)
const canSubmit = computed(() => form.currentPassword && form.newPassword.length >= 8 && !passwordMismatch.value)

async function handleSubmit() {
  if (!canSubmit.value) return
  busy.value = true
  errorText.value = ''
  try {
    await auth.changePassword({
      currentPassword: form.currentPassword,
      newPassword: form.newPassword,
    })
    await router.replace('/import')
  } catch (error) {
    errorText.value = error?.response?.data?.detail || error?.message || '修改密码失败'
  } finally {
    busy.value = false
  }
}

async function handleLogout() {
  await auth.logout()
  await router.replace('/login')
}
</script>

<template>
  <div class="auth-page">
    <section class="auth-shell auth-shell--narrow">
      <article class="auth-hero tech-card">
        <div class="auth-hero__eyebrow">First Login Check</div>
        <h1 class="auth-hero__title">先把默认口令切成你自己的平台密码。</h1>
        <p class="auth-hero__description">
          当前账号 {{ auth.currentUser?.username || '当前用户' }} 仍处于一次性密码状态。完成改密后，系统才会放行到导入层与治理控制台。
        </p>
        <div class="auth-hero__grid">
          <article class="auth-hero__item">
            <span>安全要求</span>
            <strong>新密码不少于 8 位</strong>
          </article>
          <article class="auth-hero__item">
            <span>登录路径</span>
            <strong>改密成功后自动进入导入层</strong>
          </article>
        </div>
      </article>

      <section class="auth-card tech-card">
        <div class="auth-card__eyebrow">首次登录校验</div>
        <h1 class="auth-card__title">先修改平台密码</h1>
        <p class="auth-card__description">
          当前账号 {{ auth.currentUser?.username || '当前用户' }} 仍处于一次性密码状态。完成改密后才能进入导入层与控制台。
        </p>
        <form class="auth-form" @submit.prevent="handleSubmit">
          <label class="auth-form__field">
            <span>当前密码</span>
            <input v-model="form.currentPassword" type="password" autocomplete="current-password" />
          </label>
          <label class="auth-form__field">
            <span>新密码</span>
            <input v-model="form.newPassword" type="password" autocomplete="new-password" />
          </label>
          <label class="auth-form__field">
            <span>确认新密码</span>
            <input v-model="form.confirmPassword" type="password" autocomplete="new-password" />
          </label>
          <p v-if="passwordMismatch" class="auth-form__error">两次输入的新密码不一致。</p>
          <p v-else-if="errorText" class="auth-form__error">{{ errorText }}</p>
          <div class="auth-form__actions">
            <button type="button" class="btn-tech" :disabled="busy" @click="handleLogout">
              退出登录
            </button>
            <button type="submit" class="btn-tech btn-tech--primary" :disabled="busy || !canSubmit">
              {{ busy ? '提交中...' : '修改密码并继续' }}
            </button>
          </div>
        </form>
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
  width: min(1080px, 100%);
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 420px);
  gap: 22px;
}

.auth-shell--narrow {
  width: min(1040px, 100%);
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
  font-size: clamp(2rem, 3vw, 3.2rem);
  line-height: 0.98;
  font-weight: 600;
  letter-spacing: -0.05em;
  background: linear-gradient(180deg, #ffffff 0%, rgba(237, 238, 247, 0.72) 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.auth-hero__description,
.auth-card__description {
  color: var(--text-secondary);
  line-height: 1.8;
}

.auth-hero__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
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
  font-size: 1.82rem;
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

.auth-form__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.auth-form__error {
  color: var(--accent-danger);
  font-size: 0.82rem;
  line-height: 1.6;
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

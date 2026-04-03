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
  </div>
</template>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
  background:
    radial-gradient(circle at 14% 18%, rgba(196, 30, 58, 0.08), transparent 22%),
    radial-gradient(circle at 84% 18%, rgba(46, 139, 87, 0.12), transparent 20%),
    linear-gradient(180deg, rgba(251, 247, 242, 0.98), rgba(243, 237, 228, 0.94));
}

.auth-card {
  width: min(92vw, 500px);
  padding: 28px;
  display: grid;
  gap: 14px;
}

.auth-card__eyebrow {
  font-size: 0.76rem;
  letter-spacing: 0.18em;
  color: #7d746b;
}

.auth-card__title {
  font-size: 1.76rem;
  line-height: 1.18;
}

.auth-card__description {
  color: #5e574f;
  line-height: 1.7;
}

.auth-form {
  display: grid;
  gap: 14px;
}

.auth-form__field {
  display: grid;
  gap: 8px;
}

.auth-form__field span {
  font-size: 0.84rem;
  color: #5e574f;
}

.auth-form__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.auth-form__error {
  color: #a12a3a;
}
</style>

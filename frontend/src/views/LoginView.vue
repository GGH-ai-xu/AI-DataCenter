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
        首次启动默认管理员账号固定为 `admin`，一次性临时密码会打印在后端日志中。
      </p>
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
    radial-gradient(circle at 18% 20%, rgba(46, 139, 87, 0.14), transparent 24%),
    radial-gradient(circle at 84% 16%, rgba(212, 175, 55, 0.12), transparent 18%),
    linear-gradient(180deg, rgba(251, 247, 242, 0.98), rgba(243, 237, 228, 0.94));
}

.auth-card {
  width: min(92vw, 460px);
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
  font-size: 1.8rem;
  line-height: 1.18;
}

.auth-card__description,
.auth-card__note {
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

.auth-form__error {
  color: #a12a3a;
}
</style>

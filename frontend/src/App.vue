<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import GlobalToast from './components/GlobalToast.vue'
import { setupInterceptor } from './services/api.js'
import { useAuthStore } from './stores/auth.js'


const router = useRouter()
const auth = useAuthStore()
const toastRef = ref(null)

onMounted(() => {
  setupInterceptor({
    showToast: (message, type) => {
      toastRef.value?.show(message, type)
    },
    onUnauthorized: async () => {
      auth.forceLocalLogout()
      if (router.currentRoute.value.path !== '/login') {
        await router.replace('/login')
      }
    },
    onPasswordChangeRequired: async () => {
      if (router.currentRoute.value.path !== '/change-password') {
        await router.replace('/change-password')
      }
    },
  })
})
</script>

<template>
  <router-view />
  <GlobalToast ref="toastRef" />
</template>

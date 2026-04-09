<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

onMounted(() => {
  router.replace('/governance/actions')
})
</script>

<template>
  <section class="tech-card" style="padding: 18px;">
    任务页已并入治理台，正在跳转到即时处置...
  </section>
</template>

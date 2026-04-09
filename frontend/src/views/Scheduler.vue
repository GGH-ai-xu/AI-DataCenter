<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

onMounted(() => {
  router.replace('/governance/policies')
})
</script>

<template>
  <section class="tech-card" style="padding: 18px;">
    调度页已并入治理台，正在跳转到策略治理...
  </section>
</template>

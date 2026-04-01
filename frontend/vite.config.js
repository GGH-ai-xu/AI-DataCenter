import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

const backendHttpTarget = process.env.DEV_BACKEND_URL || 'http://localhost:8000'
const backendWsTarget = process.env.DEV_BACKEND_WS_URL || 'ws://localhost:8000'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return
          if (id.includes('echarts') || id.includes('vue-echarts')) return 'vendor-echarts'
          if (id.includes('/vue/') || id.includes('@vue') || id.includes('pinia') || id.includes('vue-router')) return 'vendor-vue'
          return 'vendor'
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: backendHttpTarget,
        changeOrigin: true,
      },
      '/ws': {
        target: backendWsTarget,
        ws: true,
      },
    },
  },
})

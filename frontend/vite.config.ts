import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

// Vite 配置：Vue 插件、dev 代理 /api -> 后端、Vitest 测试环境
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
  },
})

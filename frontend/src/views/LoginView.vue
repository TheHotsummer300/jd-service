<template>
  <div class="login-container">
    <div class="login-card">
      <h1 class="login-title">🛒 电商智能客服</h1>
      <p class="login-subtitle">请输入您的用户 ID 以开始对话</p>

      <el-form @submit.prevent="handleLogin" class="login-form">
        <el-form-item>
          <el-input
            v-model="userId"
            placeholder="请输入用户 ID"
            size="large"
            clearable
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="isLoading"
            @click="handleLogin"
            class="login-button"
          >
            进入客服
          </el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '@/stores/session'

const router = useRouter()
const sessionStore = useSessionStore()

const userId = ref('1001')
const isLoading = ref(false)

async function handleLogin() {
  if (!userId.value.trim()) return

  isLoading.value = true
  try {
    sessionStore.setUserId(userId.value.trim())
    // 进入聊天页面前先加载会话列表
    await sessionStore.loadSessions()
    router.push('/chat')
  } finally {
    isLoading.value = false
  }
}
</script>

<style scoped lang="scss">
.login-container {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.login-card {
  width: 420px;
  padding: 48px 40px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
}

.login-title {
  font-size: 28px;
  font-weight: 700;
  text-align: center;
  margin-bottom: 8px;
  color: #303133;
}

.login-subtitle {
  text-align: center;
  color: #909399;
  margin-bottom: 32px;
  font-size: 14px;
}

.login-form {
  width: 100%;
}

.login-button {
  width: 100%;
}
</style>

<script setup lang="ts">
import { ref } from 'vue'

import { useChatStore } from '../stores/chat'

const chatStore = useChatStore()

// 默认用户 ID 1001
const userId = ref('1001')
const busy = ref(false)
const error = ref('')

/** 提交用户 ID，进入聊天界面；失败时展示错误提示。 */
async function submit(): Promise<void> {
  const id = userId.value.trim()
  if (!id) return
  busy.value = true
  error.value = ''
  try {
    await chatStore.enter(id)
  } catch {
    error.value = '进入失败，请确认后端服务已启动后重试'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="user-entry">
    <h2>请输入用户 ID</h2>
    <input v-model="userId" placeholder="用户 ID" />
    <button :disabled="busy || !userId.trim()" @click="submit">确定</button>
    <p v-if="error" class="error">{{ error }}</p>
  </div>
</template>

<style scoped>
.user-entry {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  height: 100vh;
}

input {
  padding: 8px 12px;
  font-size: 16px;
  width: 240px;
}

button {
  padding: 8px 24px;
  font-size: 16px;
  cursor: pointer;
}

.error {
  color: #d93026;
  font-size: 14px;
}
</style>

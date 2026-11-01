<script setup lang="ts">
import { ref } from 'vue'

import { useChatStore } from '../stores/chat'

const chatStore = useChatStore()

// 默认用户 ID 1001
const userId = ref('1001')
const busy = ref(false)

/** 提交用户 ID，进入聊天界面。 */
async function submit(): Promise<void> {
  const id = userId.value.trim()
  if (!id) return
  busy.value = true
  try {
    await chatStore.enter(id)
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
</style>

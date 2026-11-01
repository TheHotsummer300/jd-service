<script setup lang="ts">
import { ref } from 'vue'

import { useChatStore } from '../stores/chat'

const chatStore = useChatStore()
const content = ref('')

/** 发送消息；失败时恢复内容供重试（回滚已由 store 处理）。 */
async function send(): Promise<void> {
  const text = content.value.trim()
  if (!text || chatStore.sending) return
  content.value = ''
  try {
    await chatStore.sendMessage(text)
  } catch {
    content.value = text
  }
}

/** Enter 发送，Shift+Enter 换行；输入法组合期间不触发发送。 */
function onKeydown(e: KeyboardEvent): void {
  if (e.isComposing || e.keyCode === 229) return
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    void send()
  }
}
</script>

<template>
  <div class="chat-input">
    <textarea
      v-model="content"
      :disabled="!chatStore.currentSessionId || chatStore.sending"
      :placeholder="chatStore.currentSessionId ? '请输入消息' : '请先选择或新建会话'"
      @keydown="onKeydown"
    />
    <button
      :disabled="!chatStore.currentSessionId || chatStore.sending || !content.trim()"
      @click="send"
    >
      发送
    </button>
  </div>
</template>

<style scoped>
.chat-input {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid #eee;
}

textarea {
  flex: 1;
  resize: none;
  padding: 8px 12px;
  font-size: 14px;
}

button {
  padding: 8px 16px;
  cursor: pointer;
}
</style>

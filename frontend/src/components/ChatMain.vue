<template>
  <div class="chat-main">
    <!-- 顶部会话标题 -->
    <div class="chat-header">
      <span class="chat-title">
        {{ sessionTitle }}
      </span>
    </div>

    <!-- 消息列表（含内嵌选项按钮） -->
    <MessageList
      :messages="chatStore.messages"
      :is-streaming="chatStore.isStreaming"
      :streaming-content="chatStore.streamingContent"
      @option-select="handleOptionSelect"
    />

    <!-- 输入框 -->
    <ChatInput
      :is-streaming="chatStore.isStreaming"
      @send="handleSend"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useSessionStore } from '@/stores/session'
import { useChatStore } from '@/stores/chat'
import MessageList from './MessageList.vue'
import ChatInput from './ChatInput.vue'

const sessionStore = useSessionStore()
const chatStore = useChatStore()

const sessionTitle = computed(() => {
  const active = sessionStore.sessions.find(
    (s) => s.id === sessionStore.activeSessionId,
  )
  return active?.title || '新会话'
})

async function handleSend(content: string) {
  // 无活跃会话时自动创建新会话
  if (!sessionStore.activeSessionId) {
    await sessionStore.createNewSession()
    if (sessionStore.activeSessionId) {
      await chatStore.loadMessages(sessionStore.activeSessionId)
    }
  }

  // 首条消息发送后刷新会话列表以同步标题
  const isFirstMessage = !sessionStore.sessions.find(
    (s) => s.id === sessionStore.activeSessionId,
  )?.title
  await chatStore.sendMessage(content)
  if (isFirstMessage) {
    await sessionStore.loadSessions()
  }
}

async function handleOptionSelect(value: string) {
  await chatStore.selectOption(value)
}
</script>

<style scoped lang="scss">
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #fff;
}

.chat-header {
  padding: 14px 20px;
  border-bottom: 1px solid #e4e7ed;
  background: #fafafa;
}

.chat-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}
</style>

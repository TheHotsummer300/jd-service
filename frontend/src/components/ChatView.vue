<script setup lang="ts">
import { useChatStore } from '../stores/chat'
import ChatInput from './ChatInput.vue'
import MessageList from './MessageList.vue'
import SessionSidebar from './SessionSidebar.vue'

const chatStore = useChatStore()
</script>

<template>
  <div class="chat-view">
    <SessionSidebar />
    <div class="chat-main">
      <header class="chat-header">用户 ID：{{ chatStore.userId }}</header>
      <MessageList />
      <ChatInput />
    </div>
  </div>
</template>

<style scoped>
.chat-view {
  display: flex;
  height: 100vh;
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.chat-header {
  padding: 12px 16px;
  border-bottom: 1px solid #eee;
}
</style>

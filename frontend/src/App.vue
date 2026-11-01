<script setup lang="ts">
import ChatView from './components/ChatView.vue'
import UserEntryView from './components/UserEntryView.vue'
import { useChatStore } from './stores/chat'

const chatStore = useChatStore()
</script>

<template>
  <!-- 未输入用户 ID 时显示登录视图，否则进入聊天界面 -->
  <UserEntryView v-if="!chatStore.userId" />
  <ChatView v-else />
</template>

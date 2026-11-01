<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'

import { useChatStore } from '../stores/chat'
import MessageBubble from './MessageBubble.vue'

const chatStore = useChatStore()
const listEl = ref<HTMLElement | null>(null)

// 消息数量变化后滚动到底部
watch(
  () => chatStore.messages.length,
  async () => {
    await nextTick()
    listEl.value?.scrollTo({ top: listEl.value.scrollHeight })
  },
)
</script>

<template>
  <div ref="listEl" class="message-list">
    <MessageBubble v-for="message in chatStore.messages" :key="message.id" :message="message" />
  </div>
</template>

<style scoped>
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}
</style>

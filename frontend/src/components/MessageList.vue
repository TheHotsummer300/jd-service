<template>
  <div class="message-list" ref="listRef">
    <div v-if="messages.length === 0 && !isStreaming" class="empty-hint">
      <el-empty description="发送消息开始对话" :image-size="80" />
    </div>

    <MessageBubble
      v-for="msg in messages"
      :key="msg.id"
      :role="msg.role"
      :content="msg.content"
      :business-data="msg.business_data"
      @option-select="(value: string) => $emit('option-select', value)"
    />

    <!-- 流式回复中 -->
    <MessageBubble
      v-if="isStreaming && streamingContent"
      role="assistant"
      :content="streamingContent + '▊'"
      :business-data="null"
    />

    <div v-if="isStreaming && !streamingContent" class="typing-hint">
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import type { Message } from '@/types'
import MessageBubble from './MessageBubble.vue'

const props = defineProps<{
  messages: Message[]
  isStreaming: boolean
  streamingContent: string
}>()

defineEmits<{
  'option-select': [value: string]
}>()

const listRef = ref<HTMLDivElement>()

/** 自动滚动到底部 */
function scrollToBottom() {
  nextTick(() => {
    if (listRef.value) {
      listRef.value.scrollTop = listRef.value.scrollHeight
    }
  })
}

watch(
  () => [props.messages.length, props.streamingContent],
  () => scrollToBottom(),
  { deep: true },
)
</script>

<style scoped lang="scss">
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px 0;
  background: #fff;
}

.empty-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.typing-hint {
  display: flex;
  gap: 6px;
  padding: 12px 32px;
}

.typing-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #c0c4cc;
  animation: typing 1.4s infinite ease-in-out;

  &:nth-child(2) {
    animation-delay: 0.2s;
  }

  &:nth-child(3) {
    animation-delay: 0.4s;
  }
}

@keyframes typing {
  0%, 60%, 100% {
    opacity: 0.3;
    transform: scale(0.8);
  }
  30% {
    opacity: 1;
    transform: scale(1);
  }
}
</style>

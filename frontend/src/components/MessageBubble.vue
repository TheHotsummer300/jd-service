<script setup lang="ts">
import type { Message } from '../types/chat'

defineProps<{ message: Message }>()
</script>

<template>
  <div class="message-bubble" :class="message.role">
    <div class="bubble">{{ message.content }}</div>
  </div>
</template>

<style scoped>
.message-bubble {
  display: flex;
  margin: 8px 0;
}

/* assistant 靠左，user 靠右 */
.message-bubble.assistant {
  justify-content: flex-start;
}

.message-bubble.user {
  justify-content: flex-end;
}

.bubble {
  max-width: 70%;
  padding: 8px 12px;
  border-radius: 8px;
  white-space: pre-wrap;
  word-break: break-word;
}

.assistant .bubble {
  background: #f1f1f1;
}

.user .bubble {
  background: #d1e7ff;
}
</style>

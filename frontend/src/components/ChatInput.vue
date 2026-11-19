<template>
  <div class="chat-input">
    <div class="input-wrapper">
      <el-input
        v-model="inputText"
        type="textarea"
        :rows="2"
        placeholder="输入消息，按 Enter 发送..."
        resize="none"
        :disabled="isStreaming"
        @keydown.enter.exact.prevent="handleSend"
      />
      <el-button
        type="primary"
        :disabled="!inputText.trim() || isStreaming"
        :loading="isStreaming"
        @click="handleSend"
        class="send-btn"
      >
        发送
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  isStreaming: boolean
}>()

const emit = defineEmits<{
  send: [content: string]
}>()

const inputText = ref('')

function handleSend() {
  const content = inputText.value.trim()
  if (!content || props.isStreaming) return

  emit('send', content)
  inputText.value = ''
}
</script>

<style scoped lang="scss">
.chat-input {
  padding: 12px 16px;
  border-top: 1px solid #e4e7ed;
  background: #fff;
}

.input-wrapper {
  display: flex;
  gap: 10px;
  align-items: flex-end;
}

.send-btn {
  height: 58px;
  min-width: 80px;
}
</style>

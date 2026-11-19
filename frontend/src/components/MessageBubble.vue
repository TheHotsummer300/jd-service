<template>
  <div :class="['message-bubble', role]">
    <div :class="['bubble-avatar', role]">
      {{ role === 'user' ? '👤' : '🤖' }}
    </div>
    <div :class="['bubble-body', role]">
      <!-- 非 ask_slot：普通文本 -->
      <div v-if="!askSlotData" :class="['bubble-content', role]">
        <div class="bubble-text">{{ content }}</div>
      </div>

      <!-- ask_slot：提示语 + 按钮（嵌在气泡内） -->
      <div v-if="askSlotData" :class="['bubble-content', 'bubble-options-wrapper', role]">
        <div class="option-prompt">{{ askSlotData.message }}</div>
        <div class="option-buttons">
          <el-button
            v-for="opt in askSlotData.options"
            :key="opt.value"
            :disabled="opt.disabled"
            size="small"
            class="option-btn"
            @click="$emit('option-select', opt.value)"
          >
            {{ opt.label }}
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AskSlotData, BusinessActionData } from '@/types'

const props = defineProps<{
  role: 'user' | 'assistant'
  content: string
  businessData: BusinessActionData | null
}>()

defineEmits<{
  'option-select': [value: string]
}>()

const askSlotData = computed<AskSlotData | null>(() => {
  if (props.businessData?.action === 'ask_slot') {
    return props.businessData as AskSlotData
  }
  return null
})
</script>

<style scoped lang="scss">
/* ── 消息行 ── */
.message-bubble {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
  padding: 0 16px;

  &.user {
    flex-direction: row-reverse;
  }
}

.bubble-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;

  &.user { background: #e8f4fd; }
  &.assistant { background: #f0f0f0; }
}

/* ── 气泡主体 ── */
.bubble-body {
  display: flex;
  flex-direction: column;
  align-items: flex-start;

  &.user {
    max-width: 70%;
  }
}

/* ── 文本气泡 ── */
.bubble-content {
  padding: 10px 16px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;

  &.user {
    background: #409eff;
    color: #fff;
    border-bottom-right-radius: 4px;
  }

  &.assistant {
    background: #f0f0f0;
    color: #303133;
    border-bottom-left-radius: 4px;
  }
}

.bubble-text {
  white-space: pre-wrap;
  word-break: break-word;
}

/* ── ask_slot 选项区 ── */
.bubble-options-wrapper {
  padding: 12px 16px;
  min-width: 280px;
  max-width: 80vw;
}

.option-prompt {
  font-size: 13px;
  color: #606266;
  margin-bottom: 10px;
}

.option-buttons {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.option-btn {
  width: 100% !important;
  margin-left: 0 !important;
  display: flex !important;
  justify-content: flex-start !important;
  white-space: normal !important;
  word-break: break-word;
  text-align: left;
}
</style>

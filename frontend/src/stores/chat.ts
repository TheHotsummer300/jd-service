import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Message, BusinessActionData } from '@/types'
import { fetchSession, sendMessage as apiSendMessage } from '@/api/client'

export const useChatStore = defineStore('chat', () => {
  const messages = ref<Message[]>([])
  const isStreaming = ref(false)
  const streamingContent = ref('')
  const currentSessionId = ref<string | null>(null)

  /** 获取会话消息列表 */
  async function loadMessages(sessionId: string) {
    currentSessionId.value = sessionId
    const detail = await fetchSession(sessionId)
    messages.value = detail.messages
  }

  /** 发送消息 */
  async function sendMessage(content: string) {
    if (!currentSessionId.value || isStreaming.value) return

    // 添加用户消息到列表
    const userMsg: Message = {
      id: Date.now(),
      role: 'user',
      content,
      intent: null,
      slots_json: null,
      business_data: null,
      created_at: new Date().toISOString(),
    }
    messages.value.push(userMsg)

    // 开始流式回复
    isStreaming.value = true
    streamingContent.value = ''

    try {
      await apiSendMessage(
        currentSessionId.value,
        content,
        (token) => {
          streamingContent.value += token
        },
        (doneData) => {
          // business_data 已扁平化为 {action, message, options, ...}
          const businessData = doneData.business_data as BusinessActionData | null
          if (streamingContent.value || doneData.message) {
            const assistantMsg: Message = {
              id: Date.now(),
              role: 'assistant',
              content: doneData.message || streamingContent.value,
              intent: doneData.intent,
              slots_json: doneData.slots_json,
              business_data: businessData,
              created_at: new Date().toISOString(),
            }
            messages.value.push(assistantMsg)
          }
          streamingContent.value = ''
          isStreaming.value = false
        },
      )
    } catch (err) {
      console.error('发送消息失败:', err)
      isStreaming.value = false
      streamingContent.value = ''
    }
  }

  /** 用户从选项按钮中选择一个值（直接作为用户输入发送） */
  async function selectOption(value: string) {
    await sendMessage(value)
  }

  /** 清空消息 */
  function clearMessages() {
    messages.value = []
    currentSessionId.value = null
  }

  return {
    messages,
    isStreaming,
    streamingContent,
    loadMessages,
    sendMessage,
    selectOption,
    clearMessages,
  }
})

import { defineStore } from 'pinia'
import { ref } from 'vue'

import * as api from '../api/chat'
import type { Message, Session } from '../types/chat'

/** 生成乐观消息的临时 ID（不依赖 crypto，兼容 jsdom 测试环境）。 */
function nextTempId(prefix: string): string {
  return `temp-${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

/** 聊天状态：会话列表、当前会话、消息与收发流程。 */
export const useChatStore = defineStore('chat', () => {
  const userId = ref<string | null>(null)
  const sessions = ref<Session[]>([])
  const currentSessionId = ref<string | null>(null)
  const messages = ref<Message[]>([])
  const loading = ref(false)
  const sending = ref(false)

  /** 进入聊天：设置 userId 并拉取会话列表。 */
  async function enter(id: string): Promise<void> {
    userId.value = id
    await loadSessions()
  }

  /** 拉取当前用户的会话列表。 */
  async function loadSessions(): Promise<void> {
    if (!userId.value) return
    loading.value = true
    try {
      sessions.value = await api.listSessions(userId.value)
    } finally {
      loading.value = false
    }
  }

  /** 新建会话：调用后端后置顶并选中，清空消息。 */
  async function createSession(): Promise<void> {
    if (!userId.value) return
    const session = await api.createSession(userId.value)
    sessions.value = [session, ...sessions.value]
    currentSessionId.value = session.id
    messages.value = []
  }

  /** 选中会话并加载其消息。 */
  async function selectSession(id: string): Promise<void> {
    currentSessionId.value = id
    loading.value = true
    try {
      messages.value = await api.listMessages(id)
    } finally {
      loading.value = false
    }
  }

  /** 发送消息：乐观追加 user 消息，成功后追加 assistant 回复，失败回滚。 */
  async function sendMessage(content: string): Promise<void> {
    if (!currentSessionId.value) return
    const sessionId = currentSessionId.value
    const tempId = nextTempId('user')

    const userMessage: Message = {
      id: tempId,
      session_id: sessionId,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    }
    messages.value = [...messages.value, userMessage]

    sending.value = true
    try {
      const reply = await api.sendMessage(sessionId, content)
      const assistantMessage: Message = {
        id: nextTempId('assistant'),
        session_id: reply.session_id,
        role: 'assistant',
        content: reply.reply,
        intent: reply.intent,
        slots: reply.slots,
        created_at: new Date().toISOString(),
      }
      messages.value = [...messages.value, assistantMessage]
    } catch (e) {
      // 失败回滚乐观 user 消息，并向上抛出以提示
      messages.value = messages.value.filter((m) => m.id !== tempId)
      throw e
    } finally {
      sending.value = false
    }
  }

  return {
    userId,
    sessions,
    currentSessionId,
    messages,
    loading,
    sending,
    enter,
    loadSessions,
    createSession,
    selectSession,
    sendMessage,
  }
})

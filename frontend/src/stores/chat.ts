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

  // 消息加载请求序号：丢弃过期响应，避免慢响应覆盖当前会话
  let loadSeq = 0

  /** 进入聊天：设置 userId 并拉取会话列表；失败回滚 userId 并抛出。 */
  async function enter(id: string): Promise<void> {
    userId.value = id
    try {
      await loadSessions()
    } catch (e) {
      userId.value = null
      throw e
    }
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

  /** 选中会话并加载其消息；丢弃过期的慢响应。 */
  async function selectSession(id: string): Promise<void> {
    currentSessionId.value = id
    messages.value = []
    const seq = ++loadSeq
    loading.value = true
    try {
      const loaded = await api.listMessages(id)
      if (seq === loadSeq && currentSessionId.value === id) {
        messages.value = loaded
      }
    } finally {
      if (seq === loadSeq) loading.value = false
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
      // 响应返回时若已切换到其它会话，则丢弃该回复（避免串到错误会话）
      if (currentSessionId.value !== sessionId) return
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
      // 仅当仍在原会话时回滚乐观消息；否则 messages 已被切换会话替换
      if (currentSessionId.value === sessionId) {
        messages.value = messages.value.filter((m) => m.id !== tempId)
      }
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

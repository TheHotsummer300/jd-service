import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Session } from '@/types'
import { createSession, fetchSessions } from '@/api/client'

export const useSessionStore = defineStore('session', () => {
  const userId = ref('')
  const sessions = ref<Session[]>([])
  const activeSessionId = ref<string | null>(null)

  /** 设置当前用户 ID */
  function setUserId(id: string) {
    userId.value = id
  }

  /** 加载会话列表 */
  async function loadSessions() {
    if (!userId.value) return
    sessions.value = await fetchSessions(userId.value)
  }

  /** 创建新会话 */
  async function createNewSession() {
    if (!userId.value) return
    const session = await createSession(userId.value)
    sessions.value.unshift(session)
    activeSessionId.value = session.id
    return session
  }

  /** 设置当前活跃会话 */
  function setActiveSession(id: string) {
    activeSessionId.value = id
  }

  return {
    userId,
    sessions,
    activeSessionId,
    setUserId,
    loadSessions,
    createNewSession,
    setActiveSession,
  }
})

import { request } from './http'
import type { ChatResponse, Message, Session } from '../types/chat'

/** 创建会话。 */
export function createSession(userId: string): Promise<Session> {
  return request<Session>('/api/v1/sessions', { method: 'POST', body: { user_id: userId } })
}

/** 列出某用户的会话（后端按 updated_at 倒序）。 */
export function listSessions(userId: string): Promise<Session[]> {
  return request<Session[]>(`/api/v1/users/${userId}/sessions`)
}

/** 列出某会话的消息（后端按 created_at 正序）。 */
export function listMessages(sessionId: string): Promise<Message[]> {
  return request<Message[]>(`/api/v1/sessions/${sessionId}/messages`)
}

/** 发送消息并返回客服回复。 */
export function sendMessage(sessionId: string, content: string): Promise<ChatResponse> {
  return request<ChatResponse>(`/api/v1/sessions/${sessionId}/chat`, {
    method: 'POST',
    body: { content },
  })
}

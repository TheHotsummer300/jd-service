/** 会话。 */
export interface Session {
  id: string
  user_id: string
  title: string
  created_at: string
  updated_at: string
}

/** 消息角色。 */
export type Role = 'user' | 'assistant'

/** 消息。 */
export interface Message {
  id: string
  session_id: string
  role: Role
  content: string
  intent?: string | null
  slots?: Record<string, string> | null
  created_at: string
}

/** 发送消息请求体。 */
export interface ChatRequest {
  content: string
}

/** 聊天回复。 */
export interface ChatResponse {
  reply: string
  intent: string | null
  slots: Record<string, string>
  session_id: string
}

/** 后端统一响应信封。 */
export interface ApiEnvelope<T> {
  success: boolean
  data: T | null
  error: string | null
  meta: unknown
}

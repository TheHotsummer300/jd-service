/** 会话 */
export interface Session {
  id: string
  user_id: string
  title: string | null
  status: 'active' | 'closed'
  created_at: string
  updated_at: string
}

/** 统一选项条目（与后端 OptionItem 对应） */
export interface OptionItem {
  label: string
  value: string
  disabled: boolean
}

/** ask_slot 业务动作数据 */
export interface AskSlotData {
  action: 'ask_slot'
  message: string
  slot_to_fill: string
  options: OptionItem[]
}

/** completed 业务动作数据（extra 字段为动态扩展） */
export interface CompletedData {
  action: 'completed'
  message: string
  [key: string]: unknown
}

/** 业务动作联合类型 */
export type BusinessActionData = AskSlotData | CompletedData | Record<string, unknown>

/** 消息 */
export interface Message {
  id: number
  role: 'user' | 'assistant'
  content: string
  intent: string | null
  slots_json: Record<string, unknown> | null
  business_data: BusinessActionData | null
  created_at: string
}

/** 会话详情（含消息列表） */
export interface SessionDetail {
  session: Session
  messages: Message[]
}

/** 统一 API 响应信封 */
export interface APIResponse<T = unknown> {
  success: boolean
  data: T | null
  error: string | null
  meta: Record<string, unknown> | null
}

/** SSE done 事件的 JSON 数据 */
export interface DoneData {
  intent: string | null
  slots_json: Record<string, unknown> | null
  /** 已扁平化，直接是 {action, message, options, ...} */
  business_data: BusinessActionData | null
  message: string
}

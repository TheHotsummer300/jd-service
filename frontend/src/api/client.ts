import type { APIResponse, Session, SessionDetail, DoneData } from '@/types'

const BASE_URL = '/api/v1'

/** 通用 fetch 封装 */
async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })

  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `HTTP ${response.status}`)
  }

  const json: APIResponse<T> = await response.json()
  if (!json.success) {
    throw new Error(json.error || '请求失败')
  }

  return json.data as T
}

/** 创建会话 */
export async function createSession(userId: string): Promise<Session> {
  return request<Session>(`/sessions?user_id=${encodeURIComponent(userId)}`, {
    method: 'POST',
  })
}

/** 获取会话列表 */
export async function fetchSessions(userId: string): Promise<Session[]> {
  return request<Session[]>(`/sessions?user_id=${encodeURIComponent(userId)}`)
}

/** 获取会话详情及消息 */
export async function fetchSession(sessionId: string): Promise<SessionDetail> {
  return request<SessionDetail>(`/sessions/${encodeURIComponent(sessionId)}`)
}

/** 发送消息，通过 SSE 流式接收回复
 *
 * SSE 事件类型：
 * - ``message``: 回复文本片段（逐块发送，前端逐字展示）
 * - ``done``: 回复完成，附带结构化元数据
 *
 * done 事件的 data 为 JSON，包含 intent、slots_json、business_data、message 全量文本。
 * business_data 的 action 决定前端是否渲染选项按钮：
 * - ``ask_slot`` → 渲染 OptionList 让用户选择
 * - ``completed`` → 直接展示文本
 */
export async function sendMessage(
  sessionId: string,
  content: string,
  onToken: (token: string) => void,
  onDone: (doneData: DoneData) => void,
): Promise<void> {
  const url = `${BASE_URL}/sessions/${encodeURIComponent(sessionId)}/messages?content=${encodeURIComponent(content)}`

  const response = await fetch(url, { method: 'POST' })

  if (!response.ok) {
    throw new Error(`发送消息失败: HTTP ${response.status}`)
  }

  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('浏览器不支持流式读取')
  }

  const decoder = new TextDecoder()
  let buffer = ''

  // SSE 事件解析状态
  let currentEvent = ''
  let currentData = ''

  // 局部累积完整消息文本，用于 done 事件回退
  let fullMessage = ''

  function processEvent(event: string, data: string) {
    if (event === 'message' || event === '') {
      // 文本片段
      if (data) {
        fullMessage += data
        onToken(data)
      }
    } else if (event === 'done') {
      // 流结束，data 为 JSON 元数据
      try {
        const doneData: DoneData = JSON.parse(data || '{}')
        onDone(doneData)
      } catch {
        // 兼容空 data
        onDone({
          intent: null,
          slots_json: null,
          business_data: null,
          message: fullMessage,
        } as DoneData)
      }
    }
  }

  /** 遇到 event: 或空行（事件边界）时，处理上一个已积累的事件 */
  function flushEvent() {
    if (currentEvent) {
      processEvent(currentEvent, currentData)
      currentEvent = ''
      currentData = ''
    }
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (line.startsWith('event:')) {
        flushEvent()
        currentEvent = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        currentData = line.slice(5).trim()
      } else if (line === '') {
        flushEvent()
      }
    }
  }

  // 处理最后残留的事件
  flushEvent()
}

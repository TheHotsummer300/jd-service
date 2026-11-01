import type { ApiEnvelope } from '../types/chat'

/** API 请求失败（信封 success=false 或响应非 JSON）时抛出。 */
export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** 请求选项：body 会被 JSON 序列化。 */
export interface RequestOptions {
  method?: string
  body?: unknown
}

/** 发送请求并拆解统一信封，返回 data；success=false 时抛 ApiError。 */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body } = options

  const resp = await fetch(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body != null ? JSON.stringify(body) : undefined,
  })

  let envelope: ApiEnvelope<T>
  try {
    envelope = (await resp.json()) as ApiEnvelope<T>
  } catch {
    throw new ApiError('响应解析失败', resp.status)
  }

  if (!envelope.success) {
    throw new ApiError(envelope.error ?? '请求失败', resp.status)
  }

  return envelope.data as T
}

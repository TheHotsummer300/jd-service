import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, request } from './http'

describe('request（统一信封拆包）', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('success=true 时返回 data', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        status: 200,
        json: async () => ({ success: true, data: { id: '1' }, error: null, meta: null }),
      }),
    )

    const data = await request<{ id: string }>('/api/v1/test')

    expect(data).toEqual({ id: '1' })
  })

  it('success=false 时抛 ApiError，携带 error 文案与 status', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        status: 404,
        json: async () => ({ success: false, data: null, error: '资源不存在', meta: null }),
      }),
    )

    try {
      await request('/api/v1/test')
      expect.unreachable('应当抛出 ApiError')
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError)
      expect((e as ApiError).message).toBe('资源不存在')
      expect((e as ApiError).status).toBe(404)
    }
  })

  it('响应体不是合法 JSON 时抛 ApiError', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        status: 502,
        json: async () => {
          throw new Error('invalid json')
        },
      }),
    )

    await expect(request('/api/v1/test')).rejects.toBeInstanceOf(ApiError)
  })

  it('POST 时将 body 序列化为 JSON 并带上 Content-Type', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      status: 201,
      json: async () => ({ success: true, data: { id: '1' }, error: null, meta: null }),
    })
    vi.stubGlobal('fetch', mockFetch)

    await request('/api/v1/sessions', { method: 'POST', body: { user_id: '1001' } })

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/v1/sessions',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ user_id: '1001' }),
        headers: { 'Content-Type': 'application/json' },
      }),
    )
  })
})

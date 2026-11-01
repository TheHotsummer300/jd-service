import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as api from '../api/chat'
import { useChatStore } from './chat'

vi.mock('../api/chat', () => ({
  listSessions: vi.fn(),
  createSession: vi.fn(),
  listMessages: vi.fn(),
  sendMessage: vi.fn(),
}))

const session = (id: string) => ({
  id,
  user_id: '1001',
  title: '新会话',
  created_at: '2026-01-01T00:00:00',
  updated_at: '2026-01-01T00:00:00',
})

describe('useChatStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('enter 设置 userId 并拉取会话列表', async () => {
    vi.mocked(api.listSessions).mockResolvedValue([session('s1')])

    const store = useChatStore()
    await store.enter('1001')

    expect(store.userId).toBe('1001')
    expect(api.listSessions).toHaveBeenCalledWith('1001')
    expect(store.sessions).toHaveLength(1)
    expect(store.sessions[0]?.id).toBe('s1')
  })

  it('createSession 选中新会话并置顶', async () => {
    vi.mocked(api.createSession).mockResolvedValue(session('new'))

    const store = useChatStore()
    store.userId = '1001'
    await store.createSession()

    expect(api.createSession).toHaveBeenCalledWith('1001')
    expect(store.currentSessionId).toBe('new')
    expect(store.sessions[0]?.id).toBe('new')
    expect(store.messages).toHaveLength(0)
  })

  it('selectSession 设置当前会话并加载其消息', async () => {
    vi.mocked(api.listMessages).mockResolvedValue([
      { id: 'm1', session_id: 's1', role: 'user', content: 'hi', created_at: '2026-01-01T00:00:00' },
    ])

    const store = useChatStore()
    await store.selectSession('s1')

    expect(store.currentSessionId).toBe('s1')
    expect(api.listMessages).toHaveBeenCalledWith('s1')
    expect(store.messages).toHaveLength(1)
  })

  it('sendMessage 乐观追加 user 消息，成功后追加 assistant 回复', async () => {
    vi.mocked(api.sendMessage).mockResolvedValue({
      reply: '已识别【order_query】',
      intent: 'order_query',
      slots: { order_id: 'A1' },
      session_id: 's1',
    })

    const store = useChatStore()
    store.currentSessionId = 's1'
    await store.sendMessage('查订单')

    expect(store.messages).toHaveLength(2)
    expect(store.messages[0]?.role).toBe('user')
    expect(store.messages[0]?.content).toBe('查订单')
    expect(store.messages[1]?.role).toBe('assistant')
    expect(store.messages[1]?.content).toBe('已识别【order_query】')
  })

  it('sendMessage 失败回滚乐观 user 消息并抛错', async () => {
    vi.mocked(api.sendMessage).mockRejectedValue(new Error('boom'))

    const store = useChatStore()
    store.currentSessionId = 's1'

    await expect(store.sendMessage('查订单')).rejects.toThrow('boom')
    expect(store.messages).toHaveLength(0)
  })
})

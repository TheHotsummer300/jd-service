import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as api from '../api/chat'
import { useChatStore } from '../stores/chat'
import ChatInput from './ChatInput.vue'

vi.mock('../api/chat', () => ({
  listSessions: vi.fn(),
  createSession: vi.fn(),
  listMessages: vi.fn(),
  sendMessage: vi.fn(),
}))

describe('ChatInput', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.mocked(api.sendMessage).mockResolvedValue({
      reply: 'ok',
      intent: 'unknown',
      slots: {},
      session_id: 's1',
    })
  })

  it('Enter 发送当前输入内容', async () => {
    const store = useChatStore()
    store.currentSessionId = 's1'
    const wrapper = mount(ChatInput)

    await wrapper.get('textarea').setValue('你好')
    await wrapper.get('textarea').trigger('keydown', { key: 'Enter' })

    expect(api.sendMessage).toHaveBeenCalledWith('s1', '你好')
  })

  it('Shift+Enter 不发送', async () => {
    const store = useChatStore()
    store.currentSessionId = 's1'
    const wrapper = mount(ChatInput)

    await wrapper.get('textarea').setValue('你好')
    await wrapper.get('textarea').trigger('keydown', { key: 'Enter', shiftKey: true })

    expect(api.sendMessage).not.toHaveBeenCalled()
  })

  it('输入法组合期间按 Enter 不发送', async () => {
    const store = useChatStore()
    store.currentSessionId = 's1'
    const wrapper = mount(ChatInput)

    await wrapper.get('textarea').setValue('你好')
    const event = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true })
    // isComposing 是只读属性，需用 defineProperty 模拟输入法组合态
    Object.defineProperty(event, 'isComposing', { value: true })
    wrapper.get('textarea').element.dispatchEvent(event)

    expect(api.sendMessage).not.toHaveBeenCalled()
  })
})

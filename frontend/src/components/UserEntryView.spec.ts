import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as api from '../api/chat'
import { useChatStore } from '../stores/chat'
import UserEntryView from './UserEntryView.vue'

vi.mock('../api/chat', () => ({
  listSessions: vi.fn(),
  createSession: vi.fn(),
  listMessages: vi.fn(),
  sendMessage: vi.fn(),
}))

describe('UserEntryView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('输入框默认值为 1001', () => {
    const wrapper = mount(UserEntryView)

    const input = wrapper.get('input')
    expect((input.element as HTMLInputElement).value).toBe('1001')
  })

  it('点击确定触发 enter，设置 userId 并拉取会话', async () => {
    vi.mocked(api.listSessions).mockResolvedValue([])

    const wrapper = mount(UserEntryView)
    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(api.listSessions).toHaveBeenCalledWith('1001')
    expect(useChatStore().userId).toBe('1001')
  })
})

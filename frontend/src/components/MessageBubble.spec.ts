import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import MessageBubble from './MessageBubble.vue'

const base = { id: 'm1', session_id: 's1', content: '你好', created_at: '2026-01-01T00:00:00' }

describe('MessageBubble', () => {
  it('assistant 消息渲染文案并应用 assistant 对齐', () => {
    const wrapper = mount(MessageBubble, {
      props: { message: { ...base, role: 'assistant' } },
    })

    expect(wrapper.text()).toContain('你好')
    expect(wrapper.classes()).toContain('assistant')
  })

  it('user 消息应用 user 对齐', () => {
    const wrapper = mount(MessageBubble, {
      props: { message: { ...base, role: 'user' } },
    })

    expect(wrapper.classes()).toContain('user')
  })
})

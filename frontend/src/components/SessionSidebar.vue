<script setup lang="ts">
import { useChatStore } from '../stores/chat'

const chatStore = useChatStore()

/** 新建会话（失败静默，v1 不做复杂提示）。 */
async function handleCreate(): Promise<void> {
  try {
    await chatStore.createSession()
  } catch {
    /* v1 忽略错误提示 */
  }
}

/** 选中会话（失败静默）。 */
async function handleSelect(id: string): Promise<void> {
  try {
    await chatStore.selectSession(id)
  } catch {
    /* v1 忽略错误提示 */
  }
}
</script>

<template>
  <aside class="session-sidebar">
    <button class="new-session" @click="handleCreate">新建会话</button>
    <div v-if="chatStore.sessions.length === 0" class="empty">暂无会话，点击新建</div>
    <ul v-else class="session-list">
      <li
        v-for="session in chatStore.sessions"
        :key="session.id"
        class="session-item"
        :class="{ active: session.id === chatStore.currentSessionId }"
        @click="handleSelect(session.id)"
      >
        {{ session.title }}
      </li>
    </ul>
  </aside>
</template>

<style scoped>
.session-sidebar {
  width: 280px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #eee;
  overflow-y: auto;
}

.new-session {
  margin: 12px;
  padding: 8px 12px;
  cursor: pointer;
}

.empty {
  padding: 16px;
  color: #999;
  text-align: center;
}

.session-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.session-item {
  padding: 12px 16px;
  cursor: pointer;
  border-bottom: 1px solid #f5f5f5;
}

.session-item:hover {
  background: #fafafa;
}

.session-item.active {
  background: #eef4ff;
}
</style>

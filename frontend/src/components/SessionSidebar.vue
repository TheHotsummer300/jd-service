<template>
  <aside class="session-sidebar">
    <div class="sidebar-header">
      <el-button
        type="primary"
        class="new-session-btn"
        @click="handleCreateSession"
      >
        <el-icon><Plus /></el-icon>
        创建新会话
      </el-button>
    </div>

    <div class="session-list">
      <div
        v-for="session in sessionStore.sessions"
        :key="session.id"
        :class="['session-item', { active: session.id === sessionStore.activeSessionId }]"
        @click="handleSelectSession(session.id)"
      >
        <div class="session-title">
          {{ session.title || '新会话' }}
        </div>
        <div class="session-time">
          {{ formatTime(session.updated_at) }}
        </div>
      </div>

      <el-empty
        v-if="sessionStore.sessions.length === 0"
        description="暂无会话"
        :image-size="60"
      />
    </div>
  </aside>
</template>

<script setup lang="ts">
import { Plus } from '@element-plus/icons-vue'
import { useSessionStore } from '@/stores/session'
import { useChatStore } from '@/stores/chat'

const sessionStore = useSessionStore()
const chatStore = useChatStore()

/** 创建新会话 */
async function handleCreateSession() {
  await sessionStore.createNewSession()
  if (sessionStore.activeSessionId) {
    await chatStore.loadMessages(sessionStore.activeSessionId)
  }
}

/** 选择会话 */
async function handleSelectSession(sessionId: string) {
  sessionStore.setActiveSession(sessionId)
  await chatStore.loadMessages(sessionId)
}

/** 格式化时间 */
function formatTime(iso: string): string {
  const date = new Date(iso)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  if (hours < 24) return `${hours} 小时前`
  if (days < 7) return `${days} 天前`
  return date.toLocaleDateString('zh-CN')
}
</script>

<style scoped lang="scss">
.session-sidebar {
  width: 280px;
  min-width: 280px;
  height: 100vh;
  background: #f5f7fa;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid #e4e7ed;
}

.new-session-btn {
  width: 100%;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.session-item {
  padding: 12px 16px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 4px;
  transition: background 0.2s;

  &:hover {
    background: #e8ecf1;
  }

  &.active {
    background: #d9e1f2;
  }
}

.session-title {
  font-size: 14px;
  color: #303133;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}

.session-time {
  font-size: 12px;
  color: #909399;
}
</style>

<template>
  <div class="chat-view">
    <SessionSidebar />
    <ChatMain />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '@/stores/session'
import SessionSidebar from '@/components/SessionSidebar.vue'
import ChatMain from '@/components/ChatMain.vue'

const router = useRouter()
const sessionStore = useSessionStore()

onMounted(() => {
  // 如果未设置 userId，跳回登录页
  if (!sessionStore.userId) {
    router.replace('/login')
  }
})
</script>

<style scoped lang="scss">
.chat-view {
  display: flex;
  height: 100vh;
  overflow: hidden;
}
</style>

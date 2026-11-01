import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'

// 创建应用并挂载 Pinia
const app = createApp(App)
app.use(createPinia())
app.mount('#app')

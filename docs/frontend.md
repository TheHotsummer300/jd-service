# 智能客服系统 — 前端实现计划

> 前端 v1 实现规格。目标：一个可用的单页聊天界面，与后端 REST 接口联调。
> 约定：代码注释用中文，变量/组件/文件名用英文。

## 1. 目标与范围

单聊天页应用：

1. 进入后先让用户输入 `user_id`（默认 `1001`），点"确定"进入聊天界面。
2. 左侧：会话列表 + 顶部"新建会话"按钮。
3. 右侧：当前会话消息列表 + 底部输入框。
4. 客服（assistant）消息靠左，用户消息靠右。
5. 点某会话 → 右侧切换到该会话并加载其消息；发送消息使用当前 session_id。

**v1 不做**：流式输出、WebSocket、登录鉴权、用户头像/富文本、消息已读回执、GraphRAG 前端。

## 2. 技术栈

- Vue 3（Composition API + `<script setup>`）+ TypeScript + Vite + Pinia
- 不引入 Vue Router（单页两视图用条件渲染切换），保持简单
- 样式用普通 CSS（或 Scoped CSS），不引入 UI 组件库，保持轻量

## 3. 目录结构

```
frontend/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts            # 配置 dev 代理 /api -> http://127.0.0.1:8000
├── src/
│   ├── main.ts               # createApp + Pinia
│   ├── App.vue               # 按 user_id 有无切换 UserEntryView / ChatView
│   ├── api/
│   │   ├── http.ts           # fetch 封装（统一信封拆包 + 错误处理）
│   │   └── chat.ts           # 会话/消息/聊天 API 函数
│   ├── types/
│   │   └── chat.ts           # Session / Message / ChatRequest / ChatResponse / ApiEnvelope
│   ├── stores/
│   │   └── chat.ts           # useChatStore（user_id、会话列表、当前会话、消息）
│   ├── components/
│   │   ├── UserEntryView.vue # 输入 user_id，默认 1001，确定进入
│   │   ├── ChatView.vue      # 聊天主界面（侧栏 + 消息区布局）
│   │   ├── SessionSidebar.vue# 会话列表 + 新建会话按钮
│   │   ├── MessageList.vue   # 消息列表容器（自动滚动到底部）
│   │   ├── MessageBubble.vue # 单条消息气泡（assistant 左 / user 右）
│   │   └── ChatInput.vue     # 底部输入框 + 发送按钮（Enter 发送）
│   └── composables/
│       └── useChat.ts        # 组合式逻辑（可选，简单时可并入 store）
└── ...
```

## 4. 类型定义（`src/types/chat.ts`）

```ts
export interface Session {
  id: string
  user_id: string
  title: string
  created_at: string
  updated_at: string
}

export type Role = 'user' | 'assistant'

export interface Message {
  id: string
  session_id: string
  role: Role
  content: string
  intent?: string | null
  slots?: Record<string, string> | null
  created_at: string
}

export interface ChatRequest { content: string }
export interface ChatResponse {
  reply: string
  intent: string | null
  slots: Record<string, string>
  session_id: string
}

export interface ApiEnvelope<T> {
  success: boolean
  data: T | null
  error: string | null
  meta: unknown
}
```

## 5. API 客户端（`src/api/chat.ts`）

| 函数 | 后端端点 |
| --- | --- |
| `createSession(userId)` | `POST /api/v1/sessions` |
| `listSessions(userId)` | `GET /api/v1/users/{user_id}/sessions` |
| `listMessages(sessionId)` | `GET /api/v1/sessions/{session_id}/messages` |
| `sendMessage(sessionId, content)` | `POST /api/v1/sessions/{session_id}/chat` |

`http.ts`：统一封装 `fetch`，处理统一信封（`success=false` 时抛错）、JSON 序列化、`/api` 前缀由 Vite 代理转发。

## 6. 状态管理（`stores/chat.ts`，Pinia）

```ts
interface ChatState {
  userId: string | null          // 为 null 时显示 UserEntryView
  sessions: Session[]
  currentSessionId: string | null
  messages: Message[]
  loading: boolean
  sending: boolean
}
```

Actions：
- `enter(userId)`：设置 userId，拉取会话列表。
- `loadSessions()`：`listSessions`。
- `createSession()`：`createSession(userId)` 后刷新列表并选中新会话。
- `selectSession(id)`：设 currentSessionId，`listMessages` 加载消息。
- `sendMessage(content)`：先乐观追加 user 消息，调 `sendMessage`，成功后追加 assistant 回复；失败回滚/提示。

## 7. 组件交互与布局

### 7.1 UserEntryView
- 一个输入框（默认值 `1001`）+ "确定"按钮。
- 点击确定 → `chatStore.enter(userId)`。

### 7.2 ChatView（整体布局）
- 左侧 `SessionSidebar`（约 280px 固定宽），右侧消息区，整体 `display:flex` 撑满视口高度。
- 顶部工具条可显示当前 user_id。

### 7.3 SessionSidebar
- 顶部"新建会话"按钮 → `createSession()`。
- 下方会话列表（按 updated_at 倒序），当前项高亮，点击 → `selectSession(id)`。
- 空状态提示"暂无会话，点击新建"。

### 7.4 MessageList
- 渲染 `messages`；每条 `MessageBubble` 依据 `role` 决定左右对齐：
  - `assistant` 靠左（可加客服标识），`user` 靠右。
- 新消息后自动滚动到底部。

### 7.5 ChatInput
- 底部输入框 + 发送按钮；Enter 发送（Shift+Enter 换行）。
- 空内容不可发送；`sending` 时禁用。
- 未选中会话时输入框禁用并提示"请先选择或新建会话"。

## 8. 运行与联调

- `npm install`（或 `pnpm install`）。
- `npm run dev` 启动 Vite，`/api` 代理到后端 `http://127.0.0.1:8000`。
- 联调前提：后端已 `uv run uvicorn app.main:app --reload` 启动，MySQL 已 `docker compose up` 并 `alembic upgrade head`。

## 9. 测试计划

- **单元/组件测试**（Vitest + @vue/test-utils）：
  - `UserEntryView`：默认值 1001、确定触发 `enter`。
  - `MessageBubble`：`user`/`assistant` 不同对齐与文案。
  - `chat store`：mock API，断言 `enter`/`selectSession`/`sendMessage` 的状态流转与乐观更新/回滚。
- **联调验证**（手动 + 可选 E2E）：登录 → 新建会话 → 发"查订单" → 断言收到占位回复并落库。

## 10. 任务分解（按提交粒度）

| # | 任务 | 产出 | 验证 |
| --- | --- | --- | --- |
| F1 | Vite + Vue3 + TS + Pinia 脚手架 | 项目可 `npm run dev` | 页面空壳可访问 |
| F2 | types + api 客户端（http.ts / chat.ts） | 类型与请求封装 | — |
| F3 | Pinia store（chat.ts） | 状态与 actions | 单测 |
| F4 | UserEntryView + App.vue 切换 | 登录页 | 单测 |
| F5 | ChatView + SessionSidebar + MessageList + MessageBubble + ChatInput | 聊天界面 | 单测 |
| F6 | 前后端联调 + 修正 | 主流程可用 | 手动/E2E |

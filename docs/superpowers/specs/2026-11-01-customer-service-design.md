# 电商智能客服系统 — 设计 Spec

- 日期：2026-11-01
- 状态：待确认
- 范围：后端（平台 + 电商业务线）+ 前端（单聊天页）

## 1. Intent & Why（意图与动机）

构建一个可扩展的电商智能客服框架，默认内置电商业务线，作为"平台 / 业务线"分层架构的落地示例。核心要证明的是：**平台层（NLU、DM、会话管理、NLG）与业务层（电商意图逻辑）解耦**，业务线可替换、可扩展，平台永远不感知业务数据库。

v1 的验收标准是：从浏览器进入 → 输入 user_id → 新建/切换会话 → 发消息 → LLM 识别意图并抽取槽位 → 状态图流转 → 业务处理器（占位）回显 → 返回回复，整条链路端到端跑通，且分层边界不破。

## 2. Goals（目标）

1. 后端平台层完整实现：REST 通道、会话持久化（`ecs_platform`）、LLM 驱动的 NLU、LangGraph 的 DM、模板 + LLM 的 NLG。
2. 业务层定义 3 个电商意图（`order_query` / `postsale_return` / `product_inquiry`）并注册，处理器用"占位文案 + 回显槽位"实现。
3. 双库分离：平台库 `ecs_platform` 由 Alembic 管理；业务库 `ecs`（已有初始化脚本）v1 不连接、不查询。
4. 前端实现单聊天页：user_id 登录、会话列表、消息区、输入框、发送消息，与后端 REST 联调。
5. 每个实现任务通过测试后才进入下一个（覆盖目标 ≥ 80%）。

## 3. Non-Goals（非目标，v1 明确不做）

- 不做真实业务查询逻辑（订单 SQL、售后流程、商品检索均后期完善）。
- 不做 GraphRAG / Neo4j 检索（`product_inquiry` 未来走 RAG，v1 只定义意图）。
- 不做流式输出、WebSocket。
- 不做用户登录鉴权、多用户权限隔离（user_id 仅作为会话归属标识）。
- 不做前端 UI 组件库、消息富文本、已读回执、头像。
- 不做 `transfer_human` 的真实转人工逻辑（仅作为平台意图短接 fallback）。

## 4. Anti-Goals（反目标：即使技术上能跑，出现以下情况也算失败）

1. **平台感知业务库**：平台层任何代码 import 或查询 `ecs` 业务库，破坏双库分离。
2. **绕过层边界**：例如 DM 直接查库、通道层含业务逻辑、NLU 直接调用业务处理器。
3. **占位导致链路断裂**：占位处理器也必须让 nlu → slot_filling → business → response 完整跑通，不能因为"占位"而短路 DM 状态图。
4. **硬编码敏感信息**：LLM key 等不得进入代码或提交。

## 5. Constraints（约束）

- 语言/命名：代码注释、文档用中文；变量、文件名、目录名用英文。
- Python：3.12+，用 `uv` 管理依赖与虚拟环境。
- 全异步：`async def`、`AsyncSession`、`ChatOpenAI.ainvoke`。
- 日志用 `loguru`；配置用 `pydantic-settings` 读 `.env`。
- 层间通信用 Pydantic 模型。
- 平台库建表走 Alembic，不手写 DDL；业务线连接信息由业务线自己的 `config.py` 管理。
- 测试用 `pytest` + `pytest-asyncio` + `httpx`；单元测试用 SQLite(`aiosqlite`) 隔离，不依赖真实 MySQL。
- Git：任务分支开发，不自动 merge；每任务通过测试再进入下一任务。

### 环境现状（已知、需注意）

1. **`.env` 不存在**：基于 `.env.example`（`PLATFORM_DATABASE_URL` / `LLM_MODEL` / `LLM_API_KEY` / `LLM_BASE_URL` / `LOG_LEVEL`）生成 `.env` 骨架，`LLM_API_KEY` 由用户填入真实值，key 不进入任何提交。
2. **工作区有未提交的删除**：`app/*.py`、`pyproject.toml`、`tests/*`、`.env.example` 已被删（`git status` 为 `D`），`CLAUDE.md`/`.mcp.json`/`docker-compose.yaml` 有未提交改动。实现基于 `HEAD` 的脚手架恢复重建，不动用户未提交的 `CLAUDE.md`/`.mcp.json` 改动，不替用户 commit/merge。
3. **已提交的脚手架**：`app/config.py`（Settings）、`app/core/database.py`（懒加载引擎 + `get_db` 依赖）、`app/core/exceptions.py`、`app/core/logging.py`、`pyproject.toml`、`tests/` 均存在于 `HEAD`，直接恢复复用。
4. **业务库已就绪**：`docker/mysql/ecs.sql` 含 17 张表（`user_info` 1001–1010、`sku_info` 100+ 商品、`order_info`/`order_detail`/`logistics`/`postsale` 等）；`docker-compose.yaml` 起 MySQL(3307) + Neo4j。

## 6. 已敲定的决策（How）

### 6.1 整体架构

```
通道层(REST) → NLU层 → DM层(LangGraph) → 业务层 → NLG层 → 会话层
```

平台永远不感知业务数据库；每个业务线提供自己的数据库配置。层间用 Pydantic 模型通信。

### 6.2 后端分层职责

| 层 | 位置 | 职责 |
| --- | --- | --- |
| 通道层 | `app/api/` | REST 端点，无业务逻辑，统一响应信封 |
| NLU 层 | `app/nlu/` | LLM 驱动意图分类 + 槽位抽取，输出 `NLUResult` |
| DM 层 | `app/dm/` | LangGraph 状态图：entry/nlu/slot_filling/business/response/fallback |
| 业务层 | `app/business/` | 意图处理器与槽位补充提供者（唯一可替换层） |
| NLG 层 | `app/nlg/` | 模板引擎（业务结果/追问）+ LLM（闲聊/兜底） |
| 会话层 | `app/session/` | 会话/消息 ORM 与 CRUD，持久化到 `ecs_platform` |

### 6.3 意图系统

- 两级意图：平台意图（`unknown`、`transfer_human`）+ 业务意图（3 个）。
- 意图管理用「字典 + active_intent」：`DialogState.intents: dict[str, IntentContext]` 保存所有意图，`active_intent: str` 指向当前活跃意图。

**v1 业务意图与槽位定义**：

| 意图 | 描述 | 必填槽位 | 全部槽位 | 备注 |
| --- | --- | --- | --- | --- |
| `order_query` | 订单查询 | 无 | `order_id`（可选） | 无必填槽位，直接进 business 占位 |
| `postsale_return` | 售后/退货 | `order_id` | `order_id`（必填）、`postsale_type`（可选：退款/退货/换货）、`postsale_reason`（可选） | 缺 `order_id` 时追问 |
| `product_inquiry` | 商品咨询 | `product_name` | `product_name`（必填） | 未来走 RAG 检索，v1 占位 |

- 业务处理器 v1 均为占位：返回「已识别【意图】+ 槽位」，回显 `intent` 与 `slots`。
- 缺必填槽位时由 DM 的 `slot_filling` 节点生成追问（平台职责，不依赖业务代码）。
- **元数据归属（设计决策）**：意图的名称/描述/必填槽位/追问文案/枚举值由业务层定义，经注册中心（`app/business/registry.py`）暴露；NLU 的候选意图、DM 的 `slot_filling` 所需必填槽位与追问文案均从注册中心动态读取，平台不硬编码任何电商意图（保障平台/业务线解耦）。v1 实现最小注册中心：`register(intent_spec, handler)`、`get_handler(intent)`、`list_specs()`。

### 6.4 平台库数据模型（`ecs_platform`，Alembic）

**`sessions`**：`id`(UUID PK)、`user_id`(索引)、`title`(默认"新会话")、`dialog_state`(JSON 可空，多轮上下文快照)、`created_at`、`updated_at`。

**`messages`**：`id`(UUID PK)、`session_id`(FK→sessions)、`role`(enum user/assistant)、`content`(Text)、`intent`(可空)、`slots`(JSON 可空)、`created_at`。

多轮上下文恢复：从 `sessions.dialog_state` 反序列化 `DialogState`，无则新建，每轮结束回写。

### 6.5 REST API（挂 `/api/v1`，统一信封）

统一信封：`{ success, data, error, meta }`。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/sessions` | body `{user_id}`，创建会话 |
| GET | `/users/{user_id}/sessions` | 会话列表（updated_at 倒序） |
| GET | `/sessions/{session_id}/messages` | 消息列表（created_at 正序） |
| POST | `/sessions/{session_id}/chat` | body `{content}`，运行对话图，返回 `{ reply, intent, slots, session_id }` |

### 6.6 DM 状态图（LangGraph）

`DialogState`（TypedDict）字段：`session_id`、`user_id`、`user_message`、`history`、`intents`、`active_intent`、`slots`、`nlu_result`、`business_result`、`response`。

图结构：`entry → nlu → 条件路由 → { slot_filling | fallback } → business → response → END`

路由：`active_intent ∈ {unknown, transfer_human}` → fallback；否则 → slot_filling。slot_filling 缺必填槽位 → 生成追问并 END；齐 → business。

**多轮槽位填充机制（设计决策，粘性意图）**：每轮仍走 NLU 分类，但 DM 按以下规则路由：
1. 存在 `active_intent` 且必填槽位未填满时，若本轮 NLU 返回 `unknown`/低置信度，或返回意图与 `active_intent` 相同 → 保留 `active_intent`，将本轮消息送入 `slot_filling` 填缺失槽位（值优先取 NLU 抽取的 slots；为空则把整条消息作为下一个缺失槽位的值）。
2. 若 NLU 识别到新的业务意图（非 `unknown`）→ 切换 `active_intent`（旧意图快照保留在 `intents` 字典）。
3. 无 `active_intent` 或必填槽位已满 → 按 NLU 结果进入对应意图。

`IntentContext` 字段：`intent`、`slots`(dict)。顶层 `DialogState.slots` 是 `active_intent` 的当前视图，权威存储在 `intents[active_intent].slots`，每轮同步；切换意图时写回旧意图并恢复新意图。NLU 输出全量槽位，DM 合并进已有槽位（已填值不被空值覆盖）。意图取消（如"算了"）v1 不专门处理，交由 NLU 判定（通常落入 `unknown` → fallback）。

### 6.6.1 编排与事务边界（设计决策）

`POST /chat` 的编排在通道层端点完成，DM 节点自身不直接查库：
1. 会话服务读取 `sessions.dialog_state` 与消息历史；
2. 运行 DM 图（LLM 调用期间不持有数据库会话/事务）；
3. 写入 user/assistant 消息并回写 `dialog_state`。

图执行抛错时：user 消息仍落库，接口返回统一错误信封。编排逻辑放通道层端点（薄编排，非业务逻辑），v1 不新增独立应用服务层。

### 6.7 NLU / NLG 策略

- **NLU**：`ChatOpenAI.with_structured_output` 做结构化输出 `{intent, slots}`；输入 = 用户消息 + 当前 active_intent + 已填槽位 + 最近历史；候选意图 = 平台意图 + 3 业务意图；非候选或失败兜底 `unknown`。
- **LLM 提供方（设计决策）**：国内 OpenAI 兼容网关，`LLM_BASE_URL`/`LLM_MODEL`/`LLM_API_KEY` 从 `.env` 读取。结构化输出优先 function calling；若网关不支持或调用失败，降级为 JSON mode + Pydantic 校验 + 重试；仍失败则 NLU 兜底 `unknown`。
- **失败契约（设计决策）**：LLM 超时/报错/非法 JSON/key 未配置时，`POST /chat` 返回统一错误信封（`success=false`，HTTP 500），user 消息仍落库，错误详情记录到 loguru 日志。
- **NLG**：
  - 槽位追问 → `TemplateEngine`(Jinja2)；
  - 业务占位结果 → `TemplateEngine`(Jinja2)；
  - 闲聊 / unknown / fallback → `LLMGenerator`。

### 6.8 前端设计

- 技术栈：Vue 3（Composition API + `<script setup>`）+ TypeScript + Vite + Pinia；不引入 Vue Router、UI 组件库。
- 单页两视图（按 `user_id` 有无条件切换）：
  1. **UserEntryView**：输入 user_id（默认 `1001`）→ 确定进入。
  2. **ChatView**：左侧 `SessionSidebar`（会话列表 + 顶部"新建会话"），右侧 `MessageList` + 底部 `ChatInput`。
- 消息对齐：assistant 靠左、user 靠右；新消息自动滚动到底部；Enter 发送、Shift+Enter 换行；未选中会话时输入框禁用。
- Pinia store（`chat.ts`）：`userId / sessions / currentSessionId / messages / loading / sending`，actions：`enter / loadSessions / createSession / selectSession / sendMessage`（发送采用乐观追加 + 失败回滚）。
- Vite dev 代理 `/api` → `http://127.0.0.1:8000`。

### 6.9 关键取舍（已与需求方确认）

| 决策点 | 结论 |
| --- | --- |
| LLM | 国内 OpenAI 兼容网关，NLU/NLG 完全 LLM 驱动（base_url/model/key 读 `.env`） |
| 聊天传输 | REST 请求/响应（非流式、非 WebSocket） |
| 意图范围 | `order_query` / `postsale_return` / `product_inquiry` 三个 |
| 业务逻辑 | v1 占位「文案 + 回显槽位」，真实逻辑后期完善 |
| GraphRAG/Neo4j | v1 不接入；`product_inquiry` 标注未来走 RAG |

## 7. What's left to the builder（留给实现者自行决定）

以下不影响核心设计，实现者可自行定夺：

- 具体函数/类命名、模块内部组织、代码注释措辞。
- LLM 分类 prompt 的具体措辞与 few-shot 示例内容。
- Jinja2 模板文案的具体措辞。
- 前端视觉细节（颜色、间距、字体）。
- 依赖的精确版本号（`uv add` 时定）。
- ID 生成方式（uuid4 或其它）、时间字段精度。
- 测试用例的具体断言与 mock 方式。
- 会话 `title` 的生成策略（v1 默认"新会话"或取首条消息摘要）。

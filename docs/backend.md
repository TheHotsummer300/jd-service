# 电商智能客服后端 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现电商智能客服后端 v1，跑通「通道层(REST) → NLU → DM(LangGraph) → 业务层(占位) → NLG → 会话层」完整链路，会话/消息/多轮上下文持久化到 `ecs_platform`，并严格守住「平台不感知业务库」的分层边界。

**Architecture:** FastAPI 异步应用暴露 `/api/v1` REST 端点（统一信封 `{success,data,error,meta}`）；对话由 LangGraph 状态机驱动（entry→nlu→{slot_filling|fallback}→business→response），意图元数据经业务层注册中心（`app/business/registry.py`）动态暴露，平台不硬编码任何电商意图；v1 业务处理器均为「占位回显」，业务库 `ecs` 不连接、不查询。

**Tech Stack:** Python 3.12+、uv、FastAPI、LangGraph、langchain-openai(ChatOpenAI)、SQLAlchemy 2.x 异步、Alembic、Pydantic v2 + pydantic-settings、loguru、MySQL 8.0、pytest + pytest-asyncio + httpx。

**Spec:** `docs/superpowers/specs/2026-11-01-customer-service-design.md`（本计划所有接口、路径、字段、意图与槽位均以该 Spec 为准）。

## Global Constraints

- 代码注释、文档中文；变量、文件名、目录名英文。
- Python 3.12+，用 `uv` 管理依赖与虚拟环境。
- 全异步：`async def`、`AsyncSession`、`ChatOpenAI.ainvoke`。
- 日志用 `loguru`；配置用 `pydantic-settings` 读 `.env`。
- 层间通信用 Pydantic 模型，不绕过层边界。
- 平台库 `ecs_platform` 建表走 Alembic，不手写 DDL；业务线连接信息由业务线自己的 `config.py` 管理。
- 测试用 pytest + pytest-asyncio + httpx；单元测试用 SQLite(`aiosqlite`) 隔离，不依赖真实 MySQL。
- 平台永远不感知业务库：平台层任何代码不 import、不查询 `ecs` 业务库。
- v1 业务库 `ecs` 不连接、不查询；业务处理器为「占位文案 + 回显槽位」。
- 不做 GraphRAG / Neo4j 检索；不做流式输出 / WebSocket；不做鉴权（`user_id` 仅作会话归属标识）。
- `.env` 不存在，基于 `.env.example`（`PLATFORM_DATABASE_URL`/`LLM_MODEL`/`LLM_API_KEY`/`LLM_BASE_URL`/`LOG_LEVEL`）生成，`LLM_API_KEY` 由用户填真实值，key 不进入任何提交。
- 恢复 HEAD 已提交脚手架（`app/config.py`、`app/core/*`、`pyproject.toml`、`tests/*`）直接复用；不动用户未提交的 `CLAUDE.md`/`.mcp.json` 改动，不替用户 commit/merge。
- Git：任务分支开发，不自动 merge；每任务测试通过再进入下一任务。

## Review Focus

以下 5 类输入/失败模式是 Spec 隐含、但最容易咬到使用者的边界，逐条在对应任务落测试：

1. **LLM 系统失败（超时/网络错误/key 未配置）**：`POST /chat` 返回统一错误信封（`success=false`，HTTP 500），**user 消息仍落库**，错误详情只进 loguru 日志、不泄漏到响应。→ Task 4 测 `generate_text` 抛 `LLMError`；Task 9 测端点返回 500 信封且 user 消息已落库。
2. **NLU 返回非候选意图**：分类结果不在「平台意图 + 业务意图」候选集内，兜底 `unknown`，不抛 KeyError。→ Task 5 测 `classify` 返回 `unknown`。
3. **粘性意图多轮槽位填充**：`postsale_return` 缺 `order_id` 时追问；用户下一轮只回订单号，`active_intent` 不丢失、`order_id` 被填入而非重新识别意图。→ Task 8 测跨轮状态保留。
4. **空输入/非法输入**：`POST /sessions` 的 `user_id` 空白 → 422；`POST /chat` 的 `content` 空白 → 422，均不触发 LLM、不落库。→ Task 9 测。
5. **不存在的 session_id**：向不存在的会话发消息/取消息 → 404，不静默新建会话。→ Task 9 测。

## 文件结构

```
app/
├── main.py                     # FastAPI 入口：装配 graph + 注册 ecommerce，CORS，统一异常 handler，/healthz
├── config.py                   # Settings（HEAD 恢复，不改）
├── api/
│   ├── deps.py                 # get_db 依赖（复用 core.database.get_db）
│   ├── router.py               # api_router 汇总，挂 /api/v1
│   ├── schemas.py              # 统一信封 ApiResponse[success,data,error,meta]
│   └── v1/
│       ├── sessions.py         # 会话/消息查询端点
│       ├── chat.py             # POST /chat：薄编排（读状态→跑图→写回）
│       └── schemas.py          # 请求/响应 Pydantic
├── core/
│   ├── database.py             # 平台库 engine + get_db（HEAD 恢复，不改）
│   ├── exceptions.py           # AppError/NotFoundError/AppValidationError（HEAD 恢复）
│   └── logging.py              # setup_logging（HEAD 恢复，不改）
├── session/
│   ├── models.py               # ChatSession / Message ORM（UUID PK，含 dialog_state）
│   ├── schemas.py              # SessionOut / MessageOut
│   └── service.py              # SessionService CRUD + dialog_state 读写
├── llm/
│   ├── client.py               # get_chat_model / generate_text / LLMError
│   └── schemas.py              # IntentDecision 结构化 schema
├── nlu/
│   ├── platform_intents.py     # PLATFORM_INTENTS
│   ├── schemas.py              # NLUResult
│   └── classifier.py           # IntentClassifier（结构化输出 + JSON 降级 + unknown 兜底）
├── dm/
│   ├── state.py                # DialogState(TypedDict) / IntentContext / 序列化辅助
│   ├── nodes.py                # entry/nlu/slot_filling/business/response/fallback
│   ├── router.py               # route_after_nlu / route_after_slot_filling
│   └── graph.py                # build_graph()
├── nlg/
│   ├── template_engine.py      # TemplateEngine（Jinja2）
│   ├── llm_generator.py        # LLMGenerator（闲聊/兜底）
│   └── templates/              # slot_filling.j2 / business_placeholder.j2
├── business/
│   ├── registry.py             # 注册中心：IntentSpec/SlotSpec + register/get_handler/get_spec/list_specs
│   └── ecommerce/
│       ├── __init__.py         # 注册 3 个电商意图
│       ├── intents.py          # 3 个 IntentSpec（名称/描述/槽位/追问文案/枚举值）
│       └── actions.py          # 占位处理器（回显 intent + slots）
```

> v1 不建 `app/business/ecommerce/{models,repository,queries,config}.py` 与 `graphrag/`：业务库不连接、不查询（Spec Non-Goals）。

---

### Task 1: 恢复 HEAD 脚手架并验证基线

**Files:**

- 恢复：`app/__init__.py`、`app/config.py`、`app/core/__init__.py`、`app/core/database.py`、`app/core/exceptions.py`、`app/core/logging.py`、`pyproject.toml`、`.env.example`、`tests/conftest.py`、`tests/test_config.py`、`tests/test_core/test_database.py`

**Interfaces:**

- Produces（恢复后即可用，后续任务依赖，均不再改动）：
  - `Settings`：`platform_database_url: str`、`llm_model: str`、`llm_api_key: str`、`llm_base_url: str`、`log_level: str = "INFO"`（`SettingsConfigDict(env_file=".env", extra="ignore")`）
  - `Base: DeclarativeBase`
  - `create_engine(url: str) -> AsyncEngine`、`create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]`
  - `get_engine() -> AsyncEngine`、`get_session_factory() -> async_sessionmaker[AsyncSession]`、`get_db() -> AsyncIterator[AsyncSession]`
  - `AppError(Exception)`、`NotFoundError(AppError)`、`AppValidationError(AppError)`
  - `setup_logging(level: str = "INFO") -> None`

- [ ] **Step 1: 恢复被删除的文件**

```bash
git restore -- app/__init__.py app/config.py app/core/__init__.py app/core/database.py app/core/exceptions.py app/core/logging.py pyproject.toml .env.example tests/conftest.py tests/test_config.py tests/test_core/test_database.py
```

不动 `CLAUDE.md`、`.mcp.json`、`docker/docker-compose.yaml` 的未提交改动。

- [ ] **Step 2: 安装依赖并跑基线测试**

Run: `uv sync --dev && uv run pytest tests/test_config.py tests/test_core -v`
Expected: 全部 PASS（2 条：`test_settings_reads_env`、`test_engine_uses_sqlite_for_tests`）。

- [ ] **Step 3: 生成本地 `.env`（不入提交）**

```bash
cp .env.example .env
```

提示用户把 `LLM_API_KEY` 填成真实值；`.env` 已在 `.gitignore`，不 commit。

- [ ] **Step 4: Commit**

```bash
git add app/ pyproject.toml .env.example tests/
git commit -m "chore: restore scaffold from HEAD"
git log -1 --oneline   # 验证：应显示该 commit message
```

---

### Task 2: 会话层 ORM 模型（UUID 主键）与 Alembic 迁移

**Files:**

- Create: `app/session/__init__.py`, `app/session/models.py`, `alembic.ini`, `alembic/env.py`, `alembic/versions/xxxx_initial_sessions.py`
- Modify: `tests/conftest.py`（新增 SQLite 建表 fixture）

**Interfaces:**

- Consumes: `Base`（`app.core.database`）
- Produces（表结构与 Spec §6.4 一致）：
  - `ChatSession`（表 `sessions`）：`id: Mapped[uuid.UUID]`（PK，`default=uuid.uuid4`）、`user_id: Mapped[str]`（index）、`title: Mapped[str]`（`default="新会话"`）、`dialog_state: Mapped[dict | None]`（JSON 可空）、`created_at: Mapped[datetime]`（`server_default=func.now()`）、`updated_at: Mapped[datetime]`（`server_default=func.now()`、`onupdate=func.now()`）
  - `Message`（表 `messages`）：`id: Mapped[uuid.UUID]`（PK）、`session_id: Mapped[uuid.UUID]`（`ForeignKey("sessions.id")`）、`role: Mapped[str]`（取值 `user`/`assistant`）、`content: Mapped[str]`（`Text`）、`intent: Mapped[str | None]`、`slots: Mapped[dict | None]`（JSON 可空）、`created_at: Mapped[datetime]`

- [ ] **Step 1: 写失败测试** `tests/test_session/test_models.py::test_create_session_and_message`

用 SQLite 建表后：插入 `ChatSession(user_id="1001")`，断言 `id` 是 UUID、`title == "新会话"`、`dialog_state is None`；插入 `Message(session_id=..., role="user", content="hi")`，断言外键关联、`intent is None`、`slots is None`。

- [ ] **Step 2: 运行验证失败**

Run: `uv run pytest tests/test_session/test_models.py -v`
Expected: FAIL（`ChatSession`/`Message` 未定义）。

- [ ] **Step 3: 实现 `app/session/models.py`**

`id` 用 `sqlalchemy.Uuid` 类型 + `default=uuid.uuid4`（SQLite/MySQL 均映射 CHAR(32)）；JSON 字段用 `sqlalchemy.JSON`；`role` 用 `String(16)` 存储，取值 `user`/`assistant` 由应用层 Pydantic 校验。

- [ ] **Step 4: 在 `tests/conftest.py` 加建表 fixture**

提供 `async` fixture `session_factory`：用 `create_engine("sqlite+aiosqlite://")` + `Base.metadata.create_all`，测试结束 drop。供本任务及后续 service/api 测试复用。

- [ ] **Step 5: 配置 Alembic 异步迁移**

`alembic/env.py` 读 `Settings().platform_database_url`、用异步引擎跑迁移，`target_metadata = Base.metadata`。生成迁移：

```bash
uv run alembic revision --autogenerate -m "initial sessions"
```

确认迁移含 `sessions`（含 `dialog_state` JSON 列）与 `messages` 两张表、`id` 为 UUID 类型、`session_id` 外键。

- [ ] **Step 6: 运行验证通过**

Run: `uv run pytest tests/test_session/test_models.py -v`
Expected: PASS。

- [ ] **Step 7: Commit**

```bash
git add app/session/models.py alembic.ini alembic/ tests/conftest.py tests/test_session/
git commit -m "feat: add session and message models with UUID keys and alembic migration"
git log -1 --oneline   # 验证：应显示该 commit message
```

---

### Task 3: 会话层 Pydantic 模型与 CRUD 服务（含 dialog_state 读写）

**Files:**

- Create: `app/session/schemas.py`, `app/session/service.py`
- Test: `tests/test_session/test_service.py`

**Interfaces:**

- Consumes: `ChatSession`/`Message`（Task 2）、`NotFoundError`（`app.core.exceptions`）
- Produces:
  - `SessionOut(id: UUID, user_id: str, title: str, created_at: datetime, updated_at: datetime)`
  - `MessageOut(id: UUID, session_id: UUID, role: str, content: str, intent: str | None, slots: dict | None, created_at: datetime)`
  - `SessionService(session: AsyncSession)`，方法全 `async`：
    - `create_session(user_id: str) -> ChatSession`
    - `list_sessions(user_id: str) -> list[ChatSession]`（`updated_at` 倒序）
    - `get_session(session_id: UUID) -> ChatSession | None`
    - `list_messages(session_id: UUID) -> list[Message]`（`created_at` 正序）
    - `add_message(session_id: UUID, role: str, content: str, intent: str | None = None, slots: dict | None = None) -> Message`（`await session.commit()` 并刷新所属 `ChatSession.updated_at`）
    - `load_dialog_state(session_id: UUID) -> dict | None`（读 `ChatSession.dialog_state` 原始 JSON）
    - `save_dialog_state(session_id: UUID, state: dict) -> None`（写回 JSON 并 commit）

- [ ] **Step 1: 写失败测试** 三条：

`test_add_message_bumps_session_updated_at`：加消息后 session 的 `updated_at` 变大。
`test_list_sessions_ordered_by_updated_at`：两个 session，后更新的排前。
`test_dialog_state_roundtrip`：`save_dialog_state` 写 `{"active_intent": "order_query", "slots": {}}`，`load_dialog_state` 读回相等；不存在的 session 读回 `None`。

- [ ] **Step 2: 运行验证失败**

Run: `uv run pytest tests/test_session/test_service.py -v`
Expected: FAIL（`SessionService` 未定义）。

- [ ] **Step 3: 实现 `app/session/service.py` 与 `app/session/schemas.py`**

`schemas.py` 用 `model_config = ConfigDict(from_attributes=True)`，`session_id`/`id` 用 `UUID` 类型。`service.py` 中 `add_message` 内先 `add` + `flush` 取消息，再显式 `ChatSession.updated_at = func.now()` 触发 onupdate，最后 `commit`；查询用 `select().order_by(...)`。

- [ ] **Step 4: 运行验证通过**

Run: `uv run pytest tests/test_session/test_service.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add app/session/schemas.py app/session/service.py tests/test_session/test_service.py
git commit -m "feat: add session service with dialog_state persistence"
git log -1 --oneline   # 验证：应显示该 commit message
```

---

### Task 4: LLM 调用封装与结构化输出

**Files:**

- Create: `app/llm/__init__.py`, `app/llm/client.py`, `app/llm/schemas.py`
- Modify: `app/core/exceptions.py`（新增 `LLMError`）
- Test: `tests/test_llm/test_client.py`

**Interfaces:**

- Consumes: `Settings`、`AppError`
- Produces:
  - `LLMError(AppError)`（LLM 系统失败统一异常，Review Focus #1）
  - `get_chat_model() -> ChatOpenAI`（`model=settings.llm_model`、`api_key=settings.llm_api_key`、`base_url=settings.llm_base_url`、`temperature=0`；`llm_api_key` 为空或占位 `sk-your-api-key` 时抛 `LLMError`）
  - `async generate_text(prompt: str) -> str`（`await model.ainvoke(prompt)`，`except Exception` 时 loguru 记日志后 `raise LLMError`）
  - `IntentDecision(BaseModel)`：`intent: str`、`slots: dict[str, Any]`（供 `with_structured_output` 使用）

- [ ] **Step 1: 写失败测试** `test_generate_text_raises_llm_error_on_failure`

monkeypatch `ChatOpenAI.ainvoke` 抛 `Exception("timeout")`，断言 `generate_text` 抛 `LLMError`（Review Focus #1）。

- [ ] **Step 2: 写失败测试** `test_get_chat_model_raises_on_missing_key`

monkeypatch `Settings.llm_api_key` 为空，断言 `get_chat_model` 抛 `LLMError`。

- [ ] **Step 3: 运行验证失败**

Run: `uv run pytest tests/test_llm/test_client.py -v`
Expected: FAIL。

- [ ] **Step 4: 实现 `app/llm/client.py`、`app/llm/schemas.py`，并在 `app/core/exceptions.py` 加 `LLMError`**

`generate_text` 捕获 `Exception`（非 `LLMError`）统一转 `LLMError`；`get_chat_model` 先校验 key 非空且非 `sk-your-api-key` 占位。

- [ ] **Step 5: 运行验证通过**

Run: `uv run pytest tests/test_llm/test_client.py -v`
Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add app/llm/ app/core/exceptions.py tests/test_llm/
git commit -m "feat: add llm client with structured output and error contract"
git log -1 --oneline   # 验证：应显示该 commit message
```

---

### Task 5: NLU 意图分类与槽位提取

**Files:**

- Create: `app/nlu/__init__.py`, `app/nlu/platform_intents.py`, `app/nlu/schemas.py`, `app/nlu/classifier.py`
- Test: `tests/test_nlu/test_intent_classifier.py`

**Interfaces:**

- Consumes: `IntentDecision`、`LLMError`（Task 4）
- Produces:
  - `PLATFORM_INTENTS = frozenset({"unknown", "transfer_human"})`
  - `NLUResult(BaseModel)`：`intent: str`、`slots: dict[str, Any]`、`confidence: float`
  - `IntentClassifier(model: ChatOpenAI)`：
    - `async classify(text: str, active_intent: str | None, filled_slots: dict[str, Any], history: list[MessageOut], candidates: list[str]) -> NLUResult`
    - prompt 输入 = 用户消息 + 当前 `active_intent` + 已填槽位 + 最近历史 + 候选意图列表
    - 优先 `with_structured_output(IntentDecision)`；`intent` 不在 `candidates` 内 → 返回 `NLUResult(intent="unknown", slots={}, confidence=0.0)`（Review Focus #2）
    - 网关不支持 function calling 时降级 JSON mode + Pydantic 校验 + 重试；JSON 解析/校验仍失败 → 返回 `unknown`（NLU 层兜底，不抛异常）；超时/网络错误 → 透传 `LLMError`（由上层转 500）

- [ ] **Step 1: 写失败测试** `test_unknown_intent_falls_back`

monkeypatch `model.with_structured_output` 返回的可调用对象，其输出为 `IntentDecision(intent="不存在的意图", slots={})`，`candidates=["unknown","transfer_human","order_query"]`，断言 `classify` 返回 `NLUResult(intent="unknown")`（Review Focus #2）。

- [ ] **Step 2: 写失败测试** `test_classify_passes_through_llm_error`

monkeypatch 结构化输出调用抛 `LLMError`，断言 `classify` 透传 `LLMError`（不吞成 unknown）。

- [ ] **Step 3: 运行验证失败**

Run: `uv run pytest tests/test_nlu/test_intent_classifier.py -v`
Expected: FAIL。

- [ ] **Step 4: 实现 `app/nlu/classifier.py`、`schemas.py`、`platform_intents.py`**

候选意图由调用方（DM）传入，NLU 不 import 业务层、不硬编码任何电商意图。

- [ ] **Step 5: 运行验证通过**

Run: `uv run pytest tests/test_nlu/test_intent_classifier.py -v`
Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add app/nlu/ tests/test_nlu/
git commit -m "feat: add nlu intent classifier with unknown fallback"
git log -1 --oneline   # 验证：应显示该 commit message
```

---

### Task 6: 业务层注册中心、电商意图规格与占位处理器

**Files:**

- Create: `app/business/__init__.py`, `app/business/registry.py`, `app/business/ecommerce/__init__.py`, `app/business/ecommerce/intents.py`, `app/business/ecommerce/actions.py`
- Test: `tests/test_business/test_registry.py`, `tests/test_business/test_ecommerce_actions.py`

**Interfaces:**

- Produces:
  - `SlotSpec(BaseModel)`：`name: str`、`required: bool`、`description: str = ""`、`enum: list[str] | None = None`、`prompt: str = ""`（追问文案，业务层定义）
  - `IntentSpec(BaseModel)`：`name: str`、`description: str`、`slots: list[SlotSpec]`
  - registry（模块级单例 dict）：
    - `register(intent_spec: IntentSpec, handler) -> None`
    - `get_handler(intent: str) -> Callable | None`
    - `get_spec(intent: str) -> IntentSpec | None`
    - `list_specs() -> dict[str, IntentSpec]`
    - `required_slots(intent: str) -> list[str]`（返回 `required=True` 的槽位名，缺失意图返回空列表）
  - handler 约定签名：`async def handle(intent: str, slots: dict[str, Any]) -> dict[str, Any]`（返回可模板化的 dict）
  - `app/business/ecommerce/intents.py` 定义 3 个 `IntentSpec`（与 Spec §6.3 表格一致）：
    - `order_query`：槽位 `order_id`（`required=False`）；无必填槽位。
    - `postsale_return`：`order_id`（`required=True`）、`postsale_type`（`required=False`，`enum=["退款","退货","换货"]`）、`postsale_reason`（`required=False`）。
    - `product_inquiry`：`product_name`（`required=True`）。
  - `app/business/ecommerce/actions.py` 占位 handler：返回 `{"intent": intent, "slots": slots}`（回显）。
  - `app/business/ecommerce/__init__.py`：对 3 个 `IntentSpec` 逐一 `register(spec, handle)`。

- [ ] **Step 1: 写失败测试** `tests/test_business/test_registry.py::test_register_and_query`

注册一个假 `IntentSpec(name="fake", slots=[SlotSpec(name="x", required=True)])` + 假 handler，断言 `get_spec("fake")` 取回、`get_handler("fake")` 取回、`list_specs()` 含 `"fake"`、`required_slots("fake") == ["x"]`、`required_slots("nonexistent") == []`。

- [ ] **Step 2: 写失败测试** `tests/test_business/test_ecommerce_actions.py::test_ecommerce_registers_three_intents_and_placeholder`

import `app.business.ecommerce` 后：`list_specs()` 含 `order_query`/`postsale_return`/`product_inquiry`；`required_slots("postsale_return") == ["order_id"]`；`required_slots("product_inquiry") == ["product_name"]`；`required_slots("order_query") == []`；`await get_handler("order_query")("order_query", {"order_id": "A1"})` 返回 `{"intent": "order_query", "slots": {"order_id": "A1"}}`。

- [ ] **Step 3: 运行验证失败**

Run: `uv run pytest tests/test_business/ -v`
Expected: FAIL。

- [ ] **Step 4: 实现 registry.py 与 ecommerce 包**

注册中心保持平台无电商硬编码：`registry.py` 不 import `ecommerce`；`ecommerce/__init__.py` 反向 import 并注册（装配点，由 `main.py` 触发 import）。

- [ ] **Step 5: 运行验证通过**

Run: `uv run pytest tests/test_business/ -v`
Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add app/business/ tests/test_business/
git commit -m "feat: add business registry and ecommerce placeholder intents"
git log -1 --oneline   # 验证：应显示该 commit message
```

---

### Task 7: NLG 模板引擎与 LLM 生成器

**Files:**

- Create: `app/nlg/__init__.py`, `app/nlg/template_engine.py`, `app/nlg/llm_generator.py`, `app/nlg/templates/slot_filling.j2`, `app/nlg/templates/business_placeholder.j2`
- Test: `tests/test_nlg/test_template_engine.py`

**Interfaces:**

- Consumes: `generate_text`（Task 4）
- Produces:
  - `TemplateEngine`：`render(template_name: str, context: dict[str, Any]) -> str`（Jinja2 `Environment(loader=FileSystemLoader("app/nlg/templates"))`）
  - `LLMGenerator`：`async generate(prompt: str) -> str`（委托 `generate_text`，用于闲聊/unknown/fallback）
  - 模板约定（context 键名固定，供 DM 调用）：
    - `slot_filling.j2`：接收 `{slot_name, prompt, enum}`，渲染追问；`enum` 为空则不显示选项。
    - `business_placeholder.j2`：接收 `{intent, slots}`，渲染「已识别【{intent}】+ 槽位回显」。

- [ ] **Step 1: 写失败测试** `test_render_slot_filling_with_enum`

`TemplateEngine().render("slot_filling.j2", {"slot_name": "postsale_type", "prompt": "请选择售后类型", "enum": ["退款","退货","换货"]})`，断言输出含 `postsale_type`、`请选择售后类型`、三个枚举值。

- [ ] **Step 2: 写失败测试** `test_render_business_placeholder`

`render("business_placeholder.j2", {"intent": "order_query", "slots": {"order_id": "A1"}})`，断言输出含 `order_query` 与 `A1`（精确值，模板不允许幻觉）。

- [ ] **Step 3: 运行验证失败**

Run: `uv run pytest tests/test_nlg/test_template_engine.py -v`
Expected: FAIL。

- [ ] **Step 4: 实现 `template_engine.py`、`llm_generator.py` 与两张模板**

`LLMGenerator.generate` 透传 `generate_text`（失败由上层按 500 契约处理）。

- [ ] **Step 5: 运行验证通过**

Run: `uv run pytest tests/test_nlg/test_template_engine.py -v`
Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add app/nlg/ tests/test_nlg/
git commit -m "feat: add nlg template engine and llm generator"
git log -1 --oneline   # 验证：应显示该 commit message
```

---

### Task 8: DM 层 LangGraph 状态机（含粘性意图多轮填充）

**Files:**

- Create: `app/dm/__init__.py`, `app/dm/state.py`, `app/dm/nodes.py`, `app/dm/router.py`, `app/dm/graph.py`
- Test: `tests/test_dm/test_graph.py`

**Interfaces:**

- Consumes: `IntentClassifier`（Task 5）、registry（Task 6）、`TemplateEngine`/`LLMGenerator`（Task 7）、`PLATFORM_INTENTS`（Task 5）
- Produces:
  - `IntentContext(BaseModel)`：`intent: str`、`slots: dict[str, Any]`（Spec §6.6，无 `status` 字段）
  - `DialogState(TypedDict)`：`session_id: str`、`user_id: str`、`user_message: str`、`history: list[dict]`、`intents: dict[str, IntentContext]`、`active_intent: str | None`、`slots: dict[str, Any]`、`nlu_result: NLUResult | None`、`business_result: dict[str, Any] | None`、`response: str | None`
  - `dump_state(state: DialogState) -> dict`：只返回跨轮字段 `{"intents": {name: ctx.model_dump()}, "active_intent": str|None, "slots": dict}`（供 `save_dialog_state`）
  - `load_state(persisted: dict | None, session_id: str, user_id: str, user_message: str, history: list[dict]) -> DialogState`：无则新建空状态
  - 节点函数（`StateGraph` 用）：`entry_node(state) -> dict`、`nlu_node(state) -> dict`、`slot_filling_node(state) -> dict`、`business_node(state) -> dict`、`response_node(state) -> dict`、`fallback_node(state) -> dict`
  - 路由函数：`route_after_nlu(state) -> Literal["fallback","slot_filling"]`、`route_after_slot_filling(state) -> Literal["business", END]`
  - `build_graph() -> CompiledStateGraph`：`StateGraph(DialogState)`，边结构 `START→entry→nlu`，`nlu` 条件边（`route_after_nlu`）→ `fallback`/`slot_filling`，`slot_filling` 条件边（`route_after_slot_filling`）→ `business`/`END`，`business→response→END`，`fallback→END`。

**粘性意图规则（Spec §6.6，在 `nlu_node` 内实现，精确语义）：**

1. 调 `classifier.classify(user_message, active_intent, slots, history, candidates)`，`candidates = PLATFORM_INTENTS ∪ list_specs().keys()`，存 `nlu_result`。
2. 槽位合并 `merge_slots`：`nlu_result.slots` 中非空值覆盖进 `slots`，空值不覆盖已填。
3. 若 `active_intent` 是业务意图且 `required_slots(active_intent)` 未全填：
   - 若 `nlu_result.intent == active_intent` 或 `== "unknown"`：**保留** `active_intent`；若仍有缺失槽位且本轮 `nlu_result.slots` 未补全，把整条 `user_message` 作为**第一个缺失槽位**的值填入。
   - 否则（新业务意图）：写回 `intents[active_intent].slots = slots`，切换 `active_intent = nlu_result.intent`，`slots = intents.get(new).slots`（无则 `nlu_result.slots`），确保 `intents[new]` 存在。
4. 否则（无 `active_intent` 或已满）：若 `nlu_result.intent` 是业务意图 → 设 `active_intent`、初始化 `slots`/`intents`；若是平台意图 → `active_intent = nlu_result.intent`、`slots = {}`。
5. 写回 `intents`/`active_intent`/`slots`。

**`slot_filling_node`**：取 `missing = [s for s in required_slots(active_intent) if not slots.get(s)]`；非空则对第一个缺失槽位取 `SlotSpec.prompt` 与 `enum`，`TemplateEngine.render("slot_filling.j2", ...)` 写入 `response`；空则 `response` 保持 `None`。

**`route_after_nlu`**：`active_intent in PLATFORM_INTENTS` → `"fallback"`，否则 `"slot_filling"`。
**`route_after_slot_filling`**：`response is not None` → `END`（追问已生成），否则 `"business"`。
**`business_node`**：`business_result = await registry.get_handler(active_intent)(active_intent, slots)`。
**`response_node`**：`business_result` 非空 → `TemplateEngine.render("business_placeholder.j2", business_result)` 写入 `response`。
**`fallback_node`**：`response = await LLMGenerator().generate(user_message)`（闲聊/unknown/transfer_human）。

- [ ] **Step 1: 写失败测试** `test_unknown_intent_routes_to_fallback`

monkeypatch `IntentClassifier.classify` 返回 `NLUResult(intent="unknown", slots={}, confidence=0.0)`，monkeypatch `LLMGenerator.generate` 返回 `"fallback reply"`，`await build_graph().ainvoke(初始 state)`，断言 `response == "fallback reply"` 且 `business_result is None`。

- [ ] **Step 2: 写失败测试** `test_slot_filling_preserves_active_intent_across_turns`（Review Focus #3）

第一轮 monkeypatch `classify` 返回 `NLUResult(intent="postsale_return", slots={})` → 断言 `response` 含追问（`order_id`）且 `active_intent == "postsale_return"`；用 `dump_state` 持久化后再 `load_state` 进入第二轮，monkeypatch `classify` 返回 `NLUResult(intent="unknown", slots={})`、`user_message="A100"` → 断言 `active_intent` 仍为 `postsale_return`、`slots["order_id"] == "A100"`。

- [ ] **Step 3: 运行验证失败**

Run: `uv run pytest tests/test_dm/test_graph.py -v`
Expected: FAIL。

- [ ] **Step 4: 实现 `state.py`、`nodes.py`、`router.py`、`graph.py`**

`build_graph` 每次调用新建 `StateGraph`（避免跨测试共享状态）；节点函数纯函数式（返回部分状态 dict，由 LangGraph 合并），除 `business_node`/`fallback_node` 外不持有外部副作用。

- [ ] **Step 5: 运行验证通过**

Run: `uv run pytest tests/test_dm/test_graph.py -v`
Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add app/dm/ tests/test_dm/
git commit -m "feat: add dm langgraph state machine with sticky slot filling"
git log -1 --oneline   # 验证：应显示该 commit message
```

---

### Task 9: 通道层 REST 端点、统一信封与编排

**Files:**

- Create: `app/api/__init__.py`, `app/api/deps.py`, `app/api/router.py`, `app/api/schemas.py`, `app/api/v1/__init__.py`, `app/api/v1/schemas.py`, `app/api/v1/sessions.py`, `app/api/v1/chat.py`
- Test: `tests/test_api/test_chat.py`

**Interfaces:**

- Consumes: `SessionService`/`SessionOut`/`MessageOut`（Task 3）、`build_graph`/`dump_state`/`load_state`（Task 8）、`get_db`（Task 1）、`NotFoundError`/`AppValidationError`/`LLMError`（Task 1/4）
- Produces（统一信封 `ApiResponse[T](success: bool, data: T | None, error: str | None, meta: dict | None)`，路径与 Spec §6.5 一致）：
  - `POST /api/v1/sessions` body `{user_id: str}` → `201`，data=`SessionOut`；`user_id` 空白 → 422（Review Focus #4）。
  - `GET /api/v1/users/{user_id}/sessions` → `200`，data=`list[SessionOut]`（updated_at 倒序）。
  - `GET /api/v1/sessions/{session_id}/messages` → `200`，data=`list[MessageOut]`（created_at 正序）；session 不存在 → 404（Review Focus #5）。
  - `POST /api/v1/sessions/{session_id}/chat` body `{content: str}` → `200`，data=`ChatReply(reply: str, intent: str, slots: dict, session_id: UUID)`；`content` 空白 → 422；session 不存在 → 404；LLM 失败 → 500 信封 `success=false`（Review Focus #1）。
  - 请求 schema：`SessionCreate(user_id: str)`、`MessageCreate(content: str)`。

**编排（Spec §6.6.1，在 `chat.py` 端点完成，DM 节点不查库）：**

1. 打开 DB 会话，读 `session = get_session(session_id)`（无则 404）、`history = list_messages(session_id)`、`persisted = load_dialog_state(session_id)`；释放 DB 会话（结束 `async with`）。
2. 构建 `state = load_state(persisted, session_id=str(session.id), user_id=session.user_id, user_message=content, history=[m.model_dump() for m in history])`；`await graph.ainvoke(state)`（**LLM 调用期间不持有 DB 会话/事务**）。
3. 重新打开 DB 会话：`add_message(session_id, "user", content)`；若图执行抛 `LLMError` → 仍先落 user 消息、commit，然后返回 500 信封；否则 `add_message(session_id, "assistant", reply, intent=active_intent, slots=slots)`、`save_dialog_state(session_id, dump_state(result_state))`，返回 200。
4. 统一异常 handler：`NotFoundError`→404 信封、`AppValidationError`→422 信封、`LLMError`→500 信封（`error` 为通用文案，不泄漏内部细节，详情进 loguru）。

- [ ] **Step 1: 写失败测试** `test_create_session_requires_user_id`

POST `/api/v1/sessions` body `{"user_id": "  "}` → 422（httpx ASGI 客户端 + 依赖覆盖 `get_db` 为 SQLite）。

- [ ] **Step 2: 写失败测试** `test_chat_returns_assistant_reply_and_persists_two_messages`

monkeypatch `build_graph` 返回一个 fake 图（`ainvoke` 返回 `{response:"ok", active_intent:"order_query", slots:{}}`），POST `/api/v1/sessions/{id}/chat` body `{"content":"查订单"}` → 200 且 `data.reply=="ok"`；再 GET messages 断言含 user+assistant 两条。

- [ ] **Step 3: 写失败测试** `test_chat_unknown_session_404` 与 `test_chat_llm_error_500_persists_user_message`

前者：不存在的 session 发消息 → 404。后者：fake 图 `ainvoke` 抛 `LLMError` → 500、`success=false`，且 GET messages 仍含一条 user 消息（Review Focus #1）。

- [ ] **Step 4: 运行验证失败**

Run: `uv run pytest tests/test_api/test_chat.py -v`
Expected: FAIL。

- [ ] **Step 5: 实现 `api/` 各模块**

`deps.py` 直接复用 `core.database.get_db`；`router.py` 挂 `api_router` 到 `/api/v1`；端点保持薄（无业务逻辑）；`main.py` 暂不建（Task 10 建），测试用 `FastAPI()` + 手动 include router。

- [ ] **Step 6: 运行验证通过**

Run: `uv run pytest tests/test_api/test_chat.py -v`
Expected: PASS。

- [ ] **Step 7: Commit**

```bash
git add app/api/ tests/test_api/test_chat.py
git commit -m "feat: add chat rest endpoints with envelope and orchestration"
git log -1 --oneline   # 验证：应显示该 commit message
```

---

### Task 10: 应用装配与健康检查

**Files:**

- Create: `app/main.py`
- Test: `tests/test_api/test_app.py`

**Interfaces:**

- Consumes: `build_graph`（Task 8）、`app.business.ecommerce`（Task 6，触发注册）、`setup_logging`（Task 1）、异常 handler（Task 9）
- Produces: `app.main:app`（FastAPI 实例）：`lifespan` 中 `setup_logging(Settings().log_level)`；`import app.business.ecommerce` 触发意图注册；include `api_router`；`@app.get("/healthz")` 返回 `{"success": True, "data": "ok", "error": None, "meta": None}`；注册 `NotFoundError`/`AppValidationError`/`LLMError` 的统一异常 handler（与 Task 9 相同映射）；CORS 允许前端 dev 源（`http://localhost:5173`）。

- [ ] **Step 1: 写失败测试** `test_health_endpoint`

用 httpx ASGI 客户端 GET `/healthz` → 200，`data == "ok"`。

- [ ] **Step 2: 写失败测试** `test_ecommerce_intents_registered_on_startup`

import `app.main` 后断言 `list_specs()` 含 `order_query`/`postsale_return`/`product_inquiry`。

- [ ] **Step 3: 运行验证失败**

Run: `uv run pytest tests/test_api/test_app.py -v`
Expected: FAIL。

- [ ] **Step 4: 实现 `app/main.py`**

依赖 `uv run uvicorn app.main:app` 可启动。

- [ ] **Step 5: 运行验证通过**

Run: `uv run pytest tests/test_api/test_app.py -v`
Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add app/main.py tests/test_api/test_app.py
git commit -m "feat: add app assembly with health check and error handlers"
git log -1 --oneline   # 验证：应显示该 commit message
```

---

### Task 11: 端到端集成验证

**Files:**

- Create: `tests/test_api/test_chat_flow.py`

- [ ] **Step 1: 写失败测试** `test_full_chat_flow`

用假 LLM 打桩（monkeypatch `get_chat_model` 返回一个 `classify` 固定返回 `NLUResult(intent="order_query", slots={"order_id":"A1"})` 的假模型）：
创建会话（user_id="1001"）→ `GET /users/1001/sessions` 含该会话 → `POST /chat` 发「查订单」→ 返回 `reply` 含 `order_query`（占位回显）→ `GET /messages` 返回 user+assistant 两条且顺序正确 → 再次取 `sessions` 断言无异常。整条链路无异常、数据正确。

- [ ] **Step 2: 运行验证失败**

Run: `uv run pytest tests/test_api/test_chat_flow.py -v`
Expected: FAIL（端点/图尚未在集成环境装配完整时可能失败）。

- [ ] **Step 3: 运行全量测试与迁移验证**

```bash
uv run pytest -v
uv run alembic upgrade head
```

Expected: 全量测试 PASS（覆盖 Review Focus 5 条用例）；`alembic upgrade head` 对 `ecs_platform` 成功建 `sessions`/`messages` 两张表（需 MySQL 已启动：`docker compose -f docker/docker-compose.yaml up -d`）。

- [ ] **Step 4: Commit**

```bash
git add tests/test_api/test_chat_flow.py
git commit -m "test: add end-to-end chat flow test"
```

---

## 执行说明

- 单元测试全程 SQLite（`aiosqlite`），不依赖 Docker；仅 `alembic upgrade head` 与最终 MySQL 集成验证需 `docker compose -f docker/docker-compose.yaml up -d` 启动 MySQL。
- 每完成一个任务，跑 `uv run pytest -k <该任务测试关键字> -v` 通过后再 commit、再进入下一任务。
- LLM 相关测试一律 monkeypatch `ChatOpenAI`/`get_chat_model`，不发起真实网络请求。
- 全部完成后按 CLAUDE.md Git 工作流推送 feature 分支并创建 PR 到 `dev`，不自动 merge。

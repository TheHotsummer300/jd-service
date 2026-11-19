## 项目概述

电商智能客服系统 — 基于 LangGraph + FastAPI + SQLAlchemy + Pydantic + MySQL 的可扩展智能客服框架，默认内置电商业务线。

## 技术栈与工具

| 方面       | 选择                                              |
| ---------- | ------------------------------------------------- |
| Python     | 3.14+，使用 **uv** 进行包管理和虚拟环境     |
| Web 框架   | FastAPI (异步)                                    |
| 对话管理   | LangGraph StateGraph                              |
| 数据库     | MySQL 8.0，SQLAlchemy 2.x 异步 + Alembic 迁移     |
| LLM 提供者 | langchain-openai (ChatOpenAI)，通过 `.env` 配置 |
| 配置       | pydantic-settings，从 `.env` 读取               |
| 日志       | loguru                                            |
| 测试       | pytest + pytest-asyncio + httpx                   |
| 容器       | Docker Compose (MySQL + Neo4j)                    |

## 常用命令

```bash
# 虚拟环境与依赖
uv sync                    # 安装所有依赖
uv sync --dev              # 包含开发依赖
uv add <package>           # 添加依赖
uv run <command>           # 在 venv 中运行命令

# 数据库
docker compose -f docker/docker-compose.yaml up -d   # 启动 MySQL + Neo4j
docker compose -f docker/docker-compose.yaml down     # 停止服务
uv run alembic upgrade head                           # 运行迁移
uv run alembic revision --autogenerate -m "描述"      # 创建新迁移

# 测试
uv run pytest                              # 运行所有测试
uv run pytest tests/test_nlu/              # 运行单个目录
uv run pytest tests/test_nlu/test_intent_classifier.py -v  # 运行单个文件
uv run pytest -k "test_order_query"        # 按关键字运行测试

# 应用
uv run uvicorn app.main:app --reload       # 开发服务器
```

## 全局约束

- Python 环境使用 **uv** 管理（虚拟环境、依赖安装）
- 平台库 (`ecs_platform`) 建表通过 **Alembic** 管理，不手动执行 DDL
- 所有代码使用异步（`async def`、`AsyncSession`、`ChatOpenAI.ainvoke`）
- 日志使用 `loguru`
- 变量/文件名使用英文，注释使用中文
- 配置文件为 `.env`，使用 `pydantic-settings` 读取
- 所有层间通信使用 Pydantic 模型
- 业务线数据库连接信息不属于平台配置，由业务线自己的 `config.py` 管理
- 每个任务完成后必须通过测试才能进入下一个任务
- 默认集成分支为 `dev`，生产分支为 `main`
- 新功能或修复使用独立 feature/fix 分支；需要隔离时使用 `superpowers:using-git-worktrees`
- 未经用户明确授权，不自动合并到 `dev`、`main` 或用户当前分支

## Git 工作流（必须遵守）

1. 开始任务前确认目标分支，默认从 `dev` 创建任务分支。
2. 每个任务使用独立分支，例如 `feature/order-refund-flow` 或 `fix/login-timeout`。
3. 需要隔离工作区时，使用 `superpowers:using-git-worktrees` 创建或检测 worktree；所有代码修改都在任务 worktree 中完成。
4. 完成修改后运行相关测试和检查；涉及 Python、Vue、通用审查或安全审查时，按需使用 `ccpv` 的 review 命令。
5. 提交清晰、范围集中的 commit，参考 `ccpv:git-workflow` 编写 commit message 和 PR/MR 描述。
6. 推送任务分支并创建 PR/MR 到 `dev` 或约定目标分支。
7. 不自动 merge；只有用户明确授权或 PR/MR 评审、CI 通过后才能合并。
8. PR/MR 合并后再清理本地 worktree 和任务分支。

## 架构：分层设计

```
通道层 (REST / WebSocket) → NLU 层 → DM 层 (LangGraph) → 业务层 → NLG 层 → 会话层
```

| 层               | 位置              | 职责                                                                                                                                   |
| ---------------- | ----------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| **通道层** | `app/api/`      | REST + WebSocket 端点。无业务逻辑。                                                                                                    |
| **NLU 层** | `app/nlu/`      | 意图分类 + 槽位提取，由 LLM 驱动。输出标准化的 `NLUResult`。                                                                         |
| **DM 层**  | `app/dm/`       | LangGraph StateGraph：对话状态流转、条件路由、意图管理。具有 entry、nlu、slot_filling、business、response 和 fallback 节点的有状态图。 |
| **业务层** | `app/business/` | 意图处理器和槽位补充提供者。唯一可替换的层——业务线在此实现。                                                                         |
| **NLG 层** | `app/nlg/`      | 混合策略：Jinja2 模板用于精确的业务结果，LLM 用于闲聊/兜底。                                                                           |
| **会话层** | `app/session/`  | 会话/消息 ORM 模型和 CRUD 服务，持久化到 `ecs_platform`。                                                                            |

层间通信通过 Pydantic 模型强制执行。不绕过层边界。

## 双数据库分离

| 数据库           | 用途                               | 配置                                                                     |
| ---------------- | ---------------------------------- | ------------------------------------------------------------------------ |
| `ecs_platform` | 对话会话、消息历史、槽位快照       | `app/core/database.py` → `PLATFORM_DATABASE_URL`，通过 Alembic 管理 |
| `ecs`          | 电商业务数据（订单、物流、售后等） | `business/ecommerce/config.py` → `ECO_DATABASE_URL`，业务线自管     |

平台永远不感知业务数据库。每个业务线提供自己的数据库配置。

## 意图系统

**两级意图：**

- **平台意图** (`nlu/platform_intents.py`)：`unknown`、`transfer_human` — 适用于所有业务线。DM 短接到 fallback 节点。
- **业务意图** (`business/<line>/intents.py`)：`order_query`、`logistics_track`、`postsale_return`、`logistics_complaint`、`product_inquiry`等 — 特定于业务线。

意图管理使用 **字典 + active_intent**（非栈式）：`DialogState.intents: dict[str, IntentContext]` 保存所有意图，`active_intent: str` 指向当前活跃的意图。

## NLG 策略

| 场景                      | 策略                        | 原因                 |
| ------------------------- | --------------------------- | -------------------- |
| 业务操作结果（金额、ID）  | `TemplateEngine` (Jinja2) | 必须精确，不允许幻觉 |
| 带选择列表的槽位追问      | `TemplateEngine`          | 格式固定             |
| 闲聊 / 兜底回复 / unknown | `LLMGenerator`            | 需要自然灵活         |

## 项目结构（规划的）

```
.
├── app/                         # 后端主应用：FastAPI + LangGraph 客服运行链路
│   ├── main.py                  # FastAPI 应用入口
│   ├── config.py                # 平台级配置，读取 .env
│   ├── api/                     # 通道层：REST + WebSocket，统一挂载 /api/v1
│   ├── session/                 # 会话层：会话、消息、上下文持久化服务
│   ├── dm/                      # DM 层：DialogState、LangGraph 图、节点与路由
│   ├── nlu/                     # NLU 层：意图分类、槽位抽取、平台意图定义
│   ├── nlg/                     # NLG 层：模板引擎、LLM 回复生成、Jinja2 模板
│   ├── business/                # 业务层：业务线抽象、注册中心、电商业务实现
│   │   └── ecommerce/           # 电商业务线：配置、ORM、Repository、Actions、Queries、GraphRAG
│   ├── llm/                     # LLM 调用封装与结构化 Schema
│   └── core/                    # 基础设施：数据库、异常、日志
├── frontend/                    # Vue 3 + Vite + TypeScript 前端客服界面
│   ├── src/api/                 # 前端 API 客户端与聊天/会话接口
│   ├── src/components/          # 聊天容器、消息、输入框、会话侧栏等组件
│   ├── src/composables/         # useChat、useSession 等组合式逻辑
│   ├── src/stores/              # Pinia 状态管理
│   ├── src/types/               # 前后端交互 TypeScript 类型
├── tests/                       # 后端单元测试和集成测试
├── alembic/                     # 平台库 ecs_platform 的 Alembic 迁移
├── docker/                      # 本地 MySQL / Neo4j 服务、初始化 SQL 和图谱转储
│   ├── docker-compose.yaml
│   ├── mysql/                   # 平台库和电商业务库初始化脚本
│   └── neo4j/                   # Neo4j 初始化脚本、dump 和插件
├── docs/                        # 架构说明、后端/前端设计规格和任务计划
│   ├── backend/                 # 后端规格与实施计划
│   ├── frontend/                # 前端规格与实施计划
│   └── superpowers/             # Superpowers 工作流相关规格和计划
├── scripts/                     # 辅助脚本，例如自动调试
├── .github/                     # GitHub Actions 工作流
├── pyproject.toml               # Python 项目依赖、工具和 pytest 配置
└── uv.lock                      # uv 锁定依赖
```

## 插件

此项目使用两个 Claude Code 插件（在 `.claude/` 中）：

- **superpowers**：过程层（规划、TDD、调试、验证、代码审查工作流）
- **ccpv**：技术栈特定的工程支持（FastAPI、Python、SQLAlchemy/MySQL、Docker、Vue/TypeScript 审查）

当 Superpowers 技能适用时，在采取行动之前使用 `Skill` 工具调用它们。Superpowers 拥有过程；ccpv 拥有特定于堆栈的指导。

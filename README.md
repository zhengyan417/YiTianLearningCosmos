# 依天学境 (YiTian Learning Cosmos)

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![A2A Protocol](https://img.shields.io/badge/A2A-Protocol-orange.svg)](https://github.com/a2a-protocol)

一个基于 A2A 协议的多智能体学习辅助手册，面向教学与研究场景，提供文件解析、代码生成、RAG 检索、通用检索与科研助手等能力，并内置通信审计与统一错误处理体系。

## 核心特性
- A2A 互通：客户端与多服务端智能体统一采用 A2A 协议，支持 JSON-RPC、HTTP JSON 传输与推送通知。
- 多模态输入：文本、文件（PDF、DOC、图片等）均可作为任务输入。
- 任务编排：客户端 Host Agent 负责分派任务至远程智能体，支持流式输出与断点恢复。
- 企业级可观测性：统一异常体系 + 轮转日志 + A2A 通信监控模块。
- 可扩展：各智能体独立运行，端口可配置，便于横向扩展或替换模型。

## 模块一览
| 角色 | 目录 | 默认端口 | 技术栈 | 主要能力 |
| --- | --- | --- | --- | --- |
| 文件解析智能体 | `file_parse_agent` | 10001 | LlamaIndex | 文档解析、内容抽取、流式输出 |
| 代码智能体 | `code_agent` | 10002 | LangChain | 代码生成与编程辅助 |
| RAG 智能体（Doctor RAG） | `rag_agent` | 10003 | LlamaIndex + RAG | 垂直知识检索问答 |
| 搜索智能体 | `search_agent` | 10004 | LangChain | 结构化 / 网页检索，支持数据库 |
| 研究智能体 | `research_agent` | 10005 | LangChain | 研究报告生成、资料整合 |
| 客户端 Host Agent | `a2a_client/client_host_agent` | — | A2A Client + Google ADK | 任务拆解、远程智能体路由 |
| CLI 客户端 | `cli_client` | — | asyncclick + A2A Client | 交互式命令行体验 |

## 架构概览
- 前端 / CLI 通过 A2A 客户端发送任务消息，包含上下文 ID、任务 ID、消息 ID，支持附件。
- Host Agent 依据配置选择合适的远程智能体并转发，支持流式响应。
- 各服务端智能体均基于 `a2a.server` 适配器暴露 API，使用 `AgentExecutor` 执行逻辑。
- `core/a2a_monitor.py` 在客户端和服务端两端埋点，记录完整通信事件（含流式分块）。

## 快速开始
1. 准备环境  
   - Python 3.12+  
   - 可选：Docker（用于 search_agent 的数据库）  
2. 安装依赖  
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate
pip install -r requirements.txt
```
3. 配置环境变量  
```bash
cp .env.example .env
# 填写 LLM/API 密钥、端口、数据库等配置
```
4. 启动服务端（按需选择）  
```bash
# 文件解析
python file_parse_agent/__main__.py --host localhost --port 10001
# 代码助手
python code_agent/__main__.py --host localhost --port 10002
# RAG
python rag_agent/__main__.py --host localhost --port 10003
# 搜索（需先启动数据库: docker-compose up -d）
cd search_agent
python __main__.py --host localhost --port 10004
# 研究助手
python research_agent/__main__.py --host localhost --port 10005
```
5. 启动客户端  
```bash
# Web 客户端 (Google ADK)
cd a2a_client
adk web --port 8030
```
6. 访问  
在浏览器打开 `http://localhost:8030`，或使用 `cli_client` 进行命令行交互。

### 运行入口（python -m）
各智能体包均可用模块方式启动（适合 pipx/uv 安装后直接调用），路径解析由 `core/bootstrap.py` 自动完成，无需手动修改 `sys.path`：
```bash
python -m file_parse_agent --host localhost --port 10001
python -m code_agent --host localhost --port 10002
python -m rag_agent --host localhost --port 10003
python -m search_agent --host localhost --port 10004
python -m research_agent --host localhost --port 10005
```

## 配置说明（常用字段）
- 配置由 `core/settings.py`（基于 pydantic-settings）统一管理，默认读取 `.env`。
- `DASHSCOPE_API_KEY` / `DEEPSEEK_API_KEY`：大语言模型访问密钥。
- `FILE_PARSE_AGENT_URL`、`CODE_AGENT_URL`、`RAG_AGENT_URL`、`SEARCH_AGENT_URL`、`RESEARCH_AGENT_URL`：各智能体服务地址。
- `CLIENT_WEB_PORT`：Web 客户端端口。
- `SEARCH_DB_*`：搜索智能体数据库连接配置。
- 本地模型路径：`LLM_MODEL_PATH`、`EMBED_PATH`、`STORAGE_DIR`（以及 RAG 专用路径）用于离线/本地部署。

## A2A 通信监控
- 入口：`core/observability.py` 提供 `setup_logging` / `get_logger` / `monitor` 统一接口。
- 开启：设置 `ENABLE_A2A_MONITORING=true`，可选 `A2A_MONITOR_CONSOLE=true` 输出到终端。
- 日志位置：项目根目录下 `logs/a2a_communication/a2a_comm.log`（50MB 轮转，最多 10 份），不受运行时 cwd 影响。
- 记录字段：方向、端点类型、时间戳、数据大小、上下文/任务/消息 ID、智能体名、元数据、流式分块索引、数据预览。
- 安全红化：`core/security.py` 会自动对常见敏感键（token、api_key 等）做脱敏处理，日志中仅保留掩码。
- 流式约定：`core/streaming.py` 定义 `stream_protocol=1.0`，统一端点类型字段（request/response/stream_chunk/error）。
- 手动记录示例：
```python
from core.a2a_monitor import log_manual_communication
log_manual_communication(
    direction="client_to_server",
    data={"demo": "payload"},
    context_id="ctx-1",
    task_id="task-1",
    agent_name="demo_agent",
)
```

## 测试与验证
- 单元测试：`tests/test_settings.py`、`tests/test_retry_decorator.py`、`tests/test_monitor_logging.py`。
- Host 链路 E2E：`tests/e2e_host_chains.py`（可自动拉起服务并验证跨 Agent 调用链路）。
- 全流程脚本：`tests/full_project_a2a_test.py`（自动发现虚拟环境、启动 5 个服务端、执行 CLI 多轮对话、执行 Host 链路测试、执行 pytest，并输出汇总日志）。

### 本地执行（推荐顺序）
```bash
# 1) 激活虚拟环境
.venv\Scripts\activate

# 2) 基础测试
pytest -q

# 3) Host 链路联调
python tests/e2e_host_chains.py

# 4) 完整端到端（含日志归档）
python tests/full_project_a2a_test.py
```

### 全流程测试产物
- 输出目录：`logs/full_project_test/<timestamp>/`
- 关键文件：
  - `summary.json`：本轮总览（服务状态、CLI 多轮结果、Host 链路结果、pytest 结果）
  - `runner.log`：脚本运行时间线
  - `servers/*.out.log|*.err.log`：5 个服务端日志
  - `clients/*.cli.out.log|*.cli.err.log`：CLI 多轮会话日志
  - `clients/host_chain.out.log|host_chain.err.log`：Host 链路日志
  - `artifacts/pytest.out.log|pytest.err.log`：pytest 输出
  - `artifacts/a2a_communication_snapshot/a2a_comm.log`：通信日志快照

## 日志治理与清理
- 建议长期保留：
  - 最新一次成功的 `logs/full_project_test/<timestamp>/summary.json`
  - `logs/a2a_communication/a2a_comm.log`（如需追溯线上问题）
- 可按需清理：
  - 历史 `logs/full_project_test/<old_timestamp>/` 目录
  - `logs/e2e_chain_run/`、`logs/e2e_startup/`（临时联调日志）
  - 测试缓存目录（如 `tests/__pycache__/`）

## 目录结构
```
├─a2a_client/                 # 客户端及 Host Agent
├─cli_client/                 # CLI 客户端
├─code_agent/                 # 代码智能体
├─file_parse_agent/           # 文档解析智能体
├─rag_agent/                  # RAG 智能体
├─search_agent/               # 通用检索智能体
├─research_agent/             # 研究智能体
├─core/                       # 公共模块：监控、装饰器、日志配置、异常
├─tests/                      # 单元测试与联调脚本（含 full_project_a2a_test.py）
├─logs/                       # 运行日志、通信审计、自动化测试产物
├─assets/                     # 资源（图示等）
├─requirements.txt
├─pyproject.toml
└─README.md
```

## 开发提示
- 建议在虚拟环境内开发与运行。
- 如需自定义扩展，参考 `core/a2a_monitor.py` 中的装饰器模式，保持 A2A 请求链路完整性。
- 网络/LLM 调用可使用 `core.decorators.retry_on_network` 统一重试策略（基于 tenacity，默认指数退避）。
- 已提供单元测试 + Host 链路测试 + 全流程自动化脚本；建议新增能力时同步补充 `pytest` 用例并更新 `full_project_a2a_test.py` 的验证场景。
- 类型提示：在 `core/types.py` 提供跨服务数据的 TypedDict/Protocol；提供 `mypy.ini`，可用 `mypy .` 做基础静态检查（缺失类型的三方库默认忽略）。
- 依赖管理：推荐使用 `uv` / `pipx` 基于 `pyproject.toml` 安装，可按需选择 extras：`pip install .[core]`、`pip install .[server]`、`pip install .[client]`；生成锁文件可执行 `uv lock`。
- 并发/资源：统一使用 `core.async_utils.create_http_client` 创建 httpx AsyncClient（默认关闭代理，带超时），避免在入口分散配置。
- 安全/审计：默认日志已脱敏常见秘钥；如需接入鉴权，可在服务入口添加 Bearer/API Key 校验中间件（预留）。
- 流式一致性：推荐事件端点类型遵循 `core/streaming.py` 的常量，日志自动带协议版本便于排查。
- 质量门禁：已提供 `.github/workflows/ci.yml`（ruff/mypy/pytest）和 `.pre-commit-config.yaml`；本地可运行 `ruff check .`、`mypy .`、`pytest -q`。

## 许可证
本项目使用 MIT License，详见 [LICENSE](LICENSE)。

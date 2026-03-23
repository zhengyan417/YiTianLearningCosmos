# 更新日志

所有重要的项目变更都会记录在这个文件中。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [未发布]

### 新增
- 初始化项目基础架构
- 实现多智能体通信框架
- 添加文件解析、代码生成、医学RAG等功能模块

### 修改
- 优化错误处理机制
- 改进日志管理系统

### 修复
- 修复初始版本中的已知问题

## [0.0.1] - 2026-02-20
### 新增
- 项目初始化发布
- 基于A2A协议的多智能体系统
- 支持文本、文件等多种输入形式
- 集成RAG增强检索功能

## [0.1.0] - 2026-02-25
### 新增
- 搜索智能体
- 集成MCP服务与功能

## [0.2.0] - 2026-03-03
### 新增
- 研究智能体
- 通过沙盒模拟后端进行文件的增删改查
- 集成网络检索功能

## [0.3.0] - 2026-03-04
### 新增
- 新增日志监控模块，实时监控A2A Client与A2A Server实时通信的内容与时间、大小等元数据
- 引入 `core/bootstrap.py`，统一项目根路径注入，便于所有入口脚本/服务端导入共享模块
- 引入 `core/settings.py`（基于 pydantic-settings）集中管理环境变量与默认配置
- 说明 python -m 方式的运行入口，减少相对路径依赖
- 新增 `core/observability.py`，统一日志与监控入口（setup_logging / get_logger / monitor）
- `core/decorators.retry_on_network` 基于 tenacity 提供网络/LLM 调用的统一重试策略
- 新增 `core/types.py` 提供跨服务数据的 TypedDict/Protocol；新增 `mypy.ini` 便于静态检查
- `pyproject.toml` 增加 extras (core/server/client) 便于按需安装；pytest 配置移动到 pyproject
- 新增 `core/async_utils.create_http_client` 统一 httpx AsyncClient 超时与代理配置，入口复用
- 新增 `core/security.py` 自动红化敏感字段；`core/streaming.py` 统一流式端点类型与协议版本
- 新增 `examples/minimal_cli_call.sh` 最小运行示例；新增通用 `Dockerfile`（默认启动 code_agent，支持变量切换）


### 修改
- 客户端 Host Agent 及远程连接模块改用统一的路径初始化，降低重复 sys.path 设置
- `code_agent/__main__.py`、`research_agent/__main__.py` 改为依赖 bootstrap，去除局部 sys.path 注入
- README 补充模块化启动方式和配置来源说明，与路径/配置治理保持一致
- requirements 增加 pydantic-settings 依赖
- requirements 增加 tenacity 依赖，用于统一重试
- 统一包内绝对导入：修复 `code_agent`、`rag_agent`、`search_agent`、`file_parse_agent` 入口及执行器的导入错误

### 修复
- 解决在不同工作目录或代理环境下可能出现的 `ModuleNotFoundError: core` 导入问题

## [0.3.1] - 2026-03-05
### 修改
- A2A 监控日志目录改为固定项目根下 `logs/a2a_communication`，避免 cwd 变化导致日志散落
- `create_http_client` 默认提供 httpx 连接池 `Limits`，避免缺省为 None 触发异常
- `client_host_agent` 防御性路径注入，提升 ADK 下加载 `core` 的稳定性
- `code_agent`、`research_agent`、`rag_agent` 等入口继续改为包内绝对导入，兼容多工作目录运行
- 新增 CI/质量门禁：`.github/workflows/ci.yml`（ruff/mypy/pytest）、`.pre-commit-config.yaml`，并在 `pyproject.toml` 写入 ruff 配置

## [0.4.0] - 2026-03-23
### 新增
- 新增端到端全流程测试脚本 `tests/full_project_a2a_test.py`：自动发现虚拟环境、启动 5 个 A2A 服务端、执行 CLI 多轮对话、执行 Host 链路验证、执行 `pytest`，并输出 `summary.json` 汇总。
- 新增 Host 链路 E2E 脚本 `tests/e2e_host_chains.py`：覆盖跨 Agent 调度、文件工件传递、搜索与研究链路联调。
- Search Agent 新增本地兜底工具：天气查询（`wttr.in`）与网页检索兜底（DuckDuckGo），在 MCP 不可用时仍可提供结果。
- Host Agent 新增并行分发能力 `send_messages_parallel`，支持一次请求并发调用多个远程智能体。

### 修改
- 完整更新 README：补充“测试与验证”“全流程测试产物”“日志治理与清理”章节，并更新目录结构说明。
- Search Agent 启动流程支持按需后台拉起 MCP 服务（`AUTO_START_SEARCH_MCP`），并支持通过环境变量开关 MCP 客户端（`ENABLE_SEARCH_MCP_CLIENT`）。
- Search MCP Server 配置改为环境变量驱动（主机、端口、数据库连接），减少硬编码。
- Research Agent 改为更稳定的快速研究路径（检索+总结），并在未配置 `RESEARCH_FILE_PATH` 时自动回退到默认 `backend` 目录。
- 远程通信与会话管理增强：Host Agent 增加按 Agent 会话隔离、按 Agent 锁、附件自动识别与自动转发（含 artifact 回传附件）能力。
- `.env.example` 补充搜索/研究相关配置项（`TAVILY_API_KEY`、`MCP_SEARCH_SERVER_URL`、`AUTO_START_SEARCH_MCP`、`ENABLE_SEARCH_MCP_CLIENT`），并修正研究路径变量拼写。
- `uv.lock` 同步更新依赖元数据，补充 `core/server/client` 可选依赖分组。

### 修复
- 修复 A2A 监控日志在运行期切换 `log_file` 后无法正确写入的问题：`core/a2a_monitor.py` 新增 handler 自校正逻辑（`_ensure_file_handler`）。
- 修复重试装饰器测试覆盖不足问题：`tests/test_retry_decorator.py` 增加“持续失败”场景并校验重试次数，确保 `retry_on_network` 超限行为可验证。
- 修复 Search/Research 执行器异常处理导致链路中断的问题：异常时改为返回可读错误 artifact，避免直接抛出内部错误中断会话。
- 修复远程 Agent Card 获取失败时可能影响整体初始化的问题：Host Agent 改为单 Agent 失败隔离，不阻断其余可用智能体注册。

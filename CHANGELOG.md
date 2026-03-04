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

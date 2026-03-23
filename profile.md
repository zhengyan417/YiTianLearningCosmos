依天学境（YiTian Learning Cosmos）| 基于 A2A + MCP 的多智能体学习系统                           2025.12-至今
项目简介：面向个性化学习与科研辅助场景，设计并落地“Host Agent + 多专业 Agent”协同系统，覆盖文档解析、代码生成、检索与研究报告生成，实现任务拆解、工具编排与流式响应。

技术栈：Python、A2A Protocol、Google ADK、LangChain/LangGraph、MCP、PostgreSQL、Pydantic、GitHub Actions

核心贡献：
- 搭建多智能体编排层：基于 A2A Card 动态发现并接入 5 类远程 Agent，支持 JSON-RPC/HTTP 双传输与任务并发路由，完成跨 Agent 协作闭环。
- 设计会话状态管理机制：围绕 `context_id/task_id/message_id` 实现任务追踪与上下文续接，支持多轮会话与任务恢复，提升复杂任务稳定性。
- 打通 MCP 工具生态：实现 FastMCP Search Server，统一封装搜索、用户画像与历史查询能力，并接入 PostgreSQL，增强系统个性化能力。
- 完善工程化与可观测性：沉淀统一异常与重试机制，建设 A2A 全链路通信审计日志和敏感字段脱敏策略，接入 Ruff/Mypy/Pytest + CI 流程。

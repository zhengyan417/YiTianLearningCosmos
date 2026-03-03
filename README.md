# 依天学境 (YiTian Learning Cosmos) 

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![A2A Protocol](https://img.shields.io/badge/A2A-Protocol-orange.svg)](https://github.com/a2a-protocol)

一个基于A2A协议的多智能体学习辅助系统，专为学生设计的智能化学习助手平台。

![依天学境初步架构](assets/最初版本框架.png "依天学境初步架构")

## 🌟 项目特色

- **引入MCP与A2A**：支持智能体与工具以及智能体之间的通信
- **多模态支持**：支持文本、文件等多种输入形式
- **RAG增强检索**：基于检索增强生成的知识问答系统
- **本地大模型**：支持本地部署的大语言模型调用
- **专业领域支持**：涵盖代码生成、文档解析、统一管理等多个领域
- **企业级错误处理**：完善的异常处理体系和统一日志管理
- **生产就绪**：包含重试机制、健康检查和监控支持

## 🤖 核心智能体

### 1. 客户端智能体 (Client Host Agent)
- **框架**：ADK框架
- **功能**：用户交互入口，智能路由和协调其他智能体
- **特点**：统一接口管理，支持多轮对话记忆

### 2. 文件解析智能体 (File Parse Agent)
- **框架**：LlamaIndex
- **功能**：文档解析与智能问答
- **特点**：支持PDF等格式，精确行号引用，对话历史保持

### 3. RAG智能体 (RAG Agent)
- **框架**：LlamaIndex + RAG
- **功能**：检索文献辅助智能体进行回答
- **特点**：采用RAG进行特定内容的检索与生成

### 4. 代码智能体 (Code Agent)
- **框架**：LangChain
- **功能**：代码生成与编程辅助
- **特点**：支持多种编程语言，可调用远程代码服务

### 5. 搜索智能体（Search Agent）
- **框架**: LangChain
- **功能**: 搜索用户个人信息、执行网络检索
- **特点**: 采用MCP对数据库与网络检索工具进行交互

### 6. 研究智能体（Research Agent）
- **框架**: LangChain
- **功能**: 进行相关内容的研究(支持互联网检索相关内容)
- **特点**: 通过沙盒创建后端来生成研究预案和调研文件

## 🛡️ 错误处理与日志系统

项目采用现代化的企业级错误处理和日志管理体系：

### 统一异常处理
- **自定义异常类**：定义了完整的业务异常体系
- **装饰器支持**：提供 `@handle_exceptions` 装饰器简化异常处理
- **重试机制**：内置 `@retry_on_failure` 装饰器支持自动重试
- **上下文日志**：`@with_logging_context` 提供丰富的日志上下文

### 日志管理特性
- **多格式支持**：标准、详细、JSON三种日志格式
- **日志轮转**：自动日志文件分割和清理
- **彩色输出**：终端环境下友好的彩色日志显示
- **结构化日志**：JSON格式便于日志分析和监控


## 🚀 快速开始

### 1. 环境准备

```bash
# 激活虚拟环境（推荐）
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑.env文件，填入必要的API密钥和配置
```

### 2. 启动服务端

```bash
# 启动文件解析智能体
python file_parse_agent\__main__.py --host localhost --port 10001

# 启动代码智能体
python code_agent\__main__.py --host localhost --port 10002

# 启动RAG智能体
python rag_agent\__main__.py --host localhost --port 10003

# 启动检索智能体
cd search_agent
docker-compose up -d # 启动数据库
python __main__.py --host localhost --port 10004

# 启动研究智能体
python research_agent\__main__.py --host localhost --port 10005
```

### 3. 启动客户端

```bash
# 进入客户端目录
cd a2a_client

# 启动ADK Web客户端
adk web --port 8030
```

### 4. 访问界面
打开浏览器访问：`http://localhost:8030`


## 🧪 测试对话示例

### 基础功能测试
- 你这个多智能体系统有什么功能？

### 任务测试
- 帮我解析这个PDF文件:<文件路径>，告诉我Transformer的经典架构有多少个参数？                                    
- 帮我生成懒线段树的模板代码，用python实现，直接返回给我代码
- 我出现了发热、腹痛、头晕、气寒，可能是什么症状？
- 查询一下小明的专业和学历
- 帮我研究一下A2A与MCP协议的关系

## 📁 项目结构

```
04_YiTianLearningCosmos_demo/
├── a2a_client/              # 客户端应用程序
│   └── client_host_agent/   # 客户端主机代理
├── cli_client/              # 命令行客户端(用于测试单个远程A2A服务器)
├── code_agent/              # 代码生成智能体
├── rag_agent/            # RAG智能体
├── file_parse_agent/        # 文件解析智能体
├── search_agent/        # 搜索智能体
├── research_agent/        # 研究智能体
├── README.md               # 项目说明文档
└── requirements.txt         # 依赖包列表
```

## 🤝 贡献指南

欢迎提交Issue和Pull Request来改进项目！


## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 🙏 致谢

- [A2A协议](https://github.com/a2a-protocol) - 多智能体通信协议
- [LlamaIndex](https://www.llamaindex.ai/) - 文档解析和RAG框架
- [LangChain](https://github.com/langchain-ai/langchain) - 代码生成框架
- [DashScope](https://dashscope.aliyun.com/) - 大语言模型服务

<p align="center">Made with ❤️ for learning</p>
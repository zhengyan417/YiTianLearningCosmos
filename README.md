# 依天学境 (YiTian Learning Cosmos) 

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![A2A Protocol](https://img.shields.io/badge/A2A-Protocol-orange.svg)](https://github.com/a2a-protocol)

一个基于A2A协议的多智能体学习辅助系统，专为学生设计的智能化学习助手平台。

## 🌟 项目特色

- **多模态支持**：支持文本、文件等多种输入形式
- **RAG增强检索**：基于检索增强生成的知识问答系统
- **本地大模型**：支持本地部署的大语言模型调用
- **多智能体协作**：采用A2A协议实现智能体间高效通信
- **专业领域支持**：涵盖代码生成、文档解析、医学知识等多个领域
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

### 3. 医生智能体 (Doctor Agent)
- **框架**：LlamaIndex + RAG
- **功能**：中医专业知识问答
- **特点**：基于医学知识库的精准检索和引用

### 4. 代码智能体 (Code Agent)
- **框架**：LangChain
- **功能**：代码生成与编程辅助
- **特点**：支持多种编程语言，可调用远程代码服务

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

# 启动医生智能体
python docter_agent\__main__.py --host localhost --port 10003

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
- 帮我解析这个PDF文件:<文件路径名>                                       
- 帮我生成懒线段树的模板代码，用python实现，直接返回给我代码
- 我出现了发热、腹痛、头晕、气寒，可能是什么症状？

## 📁 项目结构

```
04_YiTianLearningCosmos_demo/
├── a2a_client/              # 客户端应用程序
│   └── client_host_agent/   # 客户端主机代理
├── cli_client/              # 命令行客户端(用于测试单个远程A2A服务器)
├── code_agent/              # 代码生成智能体
├── docter_agent/            # 医学RAG智能体
├── file_parse_agent/        # 文件解析智能体
├── README.md               # 项目说明文档
└── requirements.txt         # 依赖包列表
```

## ⚙️ 配置说明

主要环境变量配置：

```env
# DashScope API密钥
DASHSCOPE_API_KEY=your_api_key_here

# Llama Cloud API密钥
LLAMA_CLOUD_API_KEY=your_api_key_here

# DeepSeek API配置
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com

# 本地模型路径
LLM_MODEL_PATH=/path/to/your/model
EMBED_PATH=/path/to/embedding/model
STORAGE_DIR=/path/to/storage

# 智能体服务URL
FILE_PARSE_AGENT_URL=http://localhost:10001
CODE_AGENT_URL=http://localhost:10002
DOCTOR_AGENT_URL=http://localhost:10003
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
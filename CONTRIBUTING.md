# 贡献指南

感谢您对依天学境项目的关注！我们欢迎各种形式的贡献。

## 如何贡献

### 报告Bug
- 使用GitHub Issues报告bug
- 描述清楚重现步骤
- 提供环境信息和错误日志

### 功能建议
- 在Issues中提出新功能建议
- 详细描述使用场景和预期效果

### 代码贡献
1. Fork项目仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启Pull Request

## 开发环境设置

```bash
# 克隆仓库
git clone https://github.com/yourusername/YiTianLearningCosmos.git
cd YiTianLearningCosmos

# 安装依赖
pip install -e .

# 运行测试
python -m pytest tests/
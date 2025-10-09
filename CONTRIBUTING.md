# 贡献指南

感谢你对 Veta 项目的关注！我们欢迎任何形式的贡献。

## 🤝 如何贡献

### 报告问题

如果你发现了 bug 或有功能建议：

1. 先查看 [Issues](https://github.com/yourusername/veta/issues) 确认是否已有人提出
2. 如果没有，创建新的 Issue，详细描述：
   - Bug：复现步骤、预期行为、实际行为、环境信息
   - 功能建议：使用场景、期望功能、解决的问题

### 提交代码

1. **Fork 项目**
   ```bash
   # 点击 GitHub 页面右上角的 Fork 按钮
   ```

2. **克隆你的 Fork**
   ```bash
   git clone https://github.com/your-username/veta.git
   cd veta
   ```

3. **创建特性分支**
   ```bash
   git checkout -b feature/your-feature-name
   # 或
   git checkout -b fix/bug-description
   ```

4. **进行开发**
   - 遵循现有的代码风格
   - 添加必要的注释
   - 确保代码可以正常运行

5. **提交更改**
   ```bash
   git add .
   git commit -m "feat: add some feature"
   # 或
   git commit -m "fix: fix some bug"
   ```

   提交信息格式：
   - `feat:` 新功能
   - `fix:` Bug 修复
   - `docs:` 文档更新
   - `style:` 代码格式调整
   - `refactor:` 重构
   - `test:` 测试相关
   - `chore:` 构建/工具相关

6. **推送到你的 Fork**
   ```bash
   git push origin feature/your-feature-name
   ```

7. **创建 Pull Request**
   - 访问你的 Fork 页面
   - 点击 "New Pull Request"
   - 填写 PR 描述，说明你的更改

## 📝 开发规范

### Python 代码风格

- 遵循 PEP 8 规范
- 使用有意义的变量名和函数名
- 添加必要的文档字符串
- 保持函数简洁，单一职责

示例：
```python
def calculate_similarity(text1: str, text2: str) -> float:
    """
    计算两个文本的相似度
    
    Args:
        text1: 第一个文本
        text2: 第二个文本
        
    Returns:
        相似度分数 (0-1)
    """
    # 实现代码
    pass
```

### 前端代码风格

- 使用清晰的 CSS 类名
- JavaScript 使用 ES6+ 语法
- 添加必要的注释
- 保持代码可读性

### 提交规范

- 每个 commit 只做一件事
- 提交信息清晰明确
- 避免提交调试代码
- 不要提交配置文件中的敏感信息

## 🧪 测试

在提交 PR 之前，请确保：

1. 代码能正常运行
2. 没有引入新的 bug
3. 已测试主要功能

## 📚 文档

如果你的更改涉及：
- 新功能：更新 README.md
- 配置变更：更新 CONFIG_README.md
- API 变更：添加相应说明

## ❓ 需要帮助？

如果你在贡献过程中遇到问题：
- 查看现有的 Issues 和 Pull Requests
- 创建 Issue 寻求帮助
- 联系维护者

## 📋 检查清单

提交 PR 前请确认：

- [ ] 代码遵循项目规范
- [ ] 已添加必要的注释
- [ ] 已测试功能正常
- [ ] 已更新相关文档
- [ ] 提交信息清晰明确
- [ ] 没有提交敏感信息

感谢你的贡献！🎉


# Contributing to oscanner

[中文](#中文) | [English](#english)

---

## 中文

感谢您考虑为 oscanner 做出贡献！我们推荐使用 Gitee 的自动 PR 生成功能，这是最高效的协作方式。

### 推荐的贡献流程（Gitee 自动 PR）

1. **创建或选择 Issue**
   - 在 [Gitee Issues](https://gitee.com/zgcai/oscanner/issues) 创建新 issue 或选择现有 issue
   - 记下 issue 编号（例如：`#IDKYFO`）

2. **在 main 分支开发**
   - Clone 仓库：
     ```bash
     git clone https://gitee.com/zgcai/oscanner.git
     cd oscanner
     ```
   - 直接在 main 分支上进行修改

3. **提交时引用 Issue**
   - 在 commit message 中使用关键词关联 issue：
     ```bash
     git commit -m "fix: 修复某个问题, fix #IDKYFO"
     # 或
     git commit -m "feat: 添加新功能, 关闭 #IDKYFO"
     ```

   **关键词说明：**
   - `fix #issue_number` - 修复 bug
   - `关闭 #issue_number` - 关闭 issue
   - `closes #issue_number` - 关闭 issue
   - `resolve #issue_number` - 解决 issue

4. **推送到远程**
   ```bash
   git push origin main
   ```

5. **自动生成 PR**
   - Gitee 会自动创建 Pull Request
   - PR 会自动关联到引用的 issue
   - 当 PR 合并时，关联的 issue 会自动关闭

### 无 Issue 时的提交

如果不需要关联 issue，使用标准的 commit message：

```bash
git commit -m "docs: 更新文档"
git commit -m "refactor: 重构代码结构"
```

### Commit Message 规范

推荐使用 [Conventional Commits](https://www.conventionalcommits.org/) 格式：

```
<type>: <description>

[optional body]
```

**常用 type:**
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `refactor`: 代码重构
- `test`: 测试相关
- `chore`: 构建/工具链更新

### 开发环境配置

参考 [README.md](README.md) 中的快速开始部分：

```bash
# 安装依赖
uv lock
uv sync

# 配置环境变量
uv run oscanner init

# 启动开发环境
uv run oscanner dev --reload --install
```

### 代码质量

- 遵循项目现有的代码风格
- 添加必要的测试
- 确保所有测试通过
- 更新相关文档

---

## English

Thank you for considering contributing to oscanner! We recommend using Gitee's auto-generated PR feature for the most efficient collaboration.

### Recommended Contribution Workflow (Gitee Auto PR)

1. **Create or Select an Issue**
   - Create a new issue or select an existing one on [Gitee Issues](https://gitee.com/zgcai/oscanner/issues)
   - Note the issue number (e.g., `#IDKYFO`)

2. **Develop on main Branch**
   - Clone the repository:
     ```bash
     git clone https://gitee.com/zgcai/oscanner.git
     cd oscanner
     ```
   - Make changes directly on the main branch

3. **Reference Issue in Commit**
   - Use keywords in commit message to link the issue:
     ```bash
     git commit -m "fix: resolve some bug, fix #IDKYFO"
     # or
     git commit -m "feat: add new feature, closes #IDKYFO"
     ```

   **Keywords:**
   - `fix #issue_number` - Fix a bug
   - `closes #issue_number` - Close an issue
   - `关闭 #issue_number` - Close an issue (Chinese)
   - `resolve #issue_number` - Resolve an issue

4. **Push to Remote**
   ```bash
   git push origin main
   ```

5. **Auto-Generated PR**
   - Gitee automatically creates a Pull Request
   - PR is automatically linked to the referenced issue
   - Issue closes automatically when PR is merged

### Commits Without Issue

If no issue reference is needed, use standard commit messages:

```bash
git commit -m "docs: update documentation"
git commit -m "refactor: restructure code"
```

### Commit Message Convention

We recommend [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>: <description>

[optional body]
```

**Common types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation update
- `refactor`: Code refactoring
- `test`: Testing related
- `chore`: Build/toolchain updates

### Development Setup

See the Quick Start section in [README.md](README.md):

```bash
# Install dependencies
uv lock
uv sync

# Configure environment
uv run oscanner init

# Start development environment
uv run oscanner dev --reload --install
```

### Code Quality

- Follow existing code style
- Add necessary tests
- Ensure all tests pass
- Update relevant documentation

---

## Resources

- [Gitee PR-Issue Linking Guide](https://help.gitee.com/base/issue/PR)
- [Gitee Auto PR Feature](https://gitee.com/help/articles/4346)
- [Conventional Commits](https://www.conventionalcommits.org/)

## Questions?

Feel free to create an issue for any questions or suggestions!

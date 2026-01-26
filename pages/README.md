# oscanner - Gitee Pages

这是 oscanner 项目的官方网站，使用 Jekyll 静态站点生成器构建。

## 在线访问

- **Gitee Pages**: https://zgcai.gitee.io/oscanner
- **GitHub Pages**: https://bjzgcai.github.io/oscanner

## 本地开发

### 前置要求

- Ruby 2.7+ 
- Bundler

### 快速开始

```bash
# 1. 进入站点目录
cd docs

# 2. 安装依赖
bundle install

# 3. 启动本地服务器
bundle exec jekyll serve

# 4. 访问 http://localhost:4000
```

### 构建静态文件

```bash
cd docs
bundle exec jekyll build
```

生成的文件在 `_site/` 目录。

## 部署

### GitHub Pages（自动部署）

1. **推送代码到 GitHub**：
   ```bash
   git add .
   git commit -m "Update Gitee Pages"
   git push origin main
   ```

2. **启用 GitHub Pages**：
   - 进入仓库 Settings → Pages
   - Source 选择 "GitHub Actions"
   - 等待自动部署完成（约 1-2 分钟）

### Gitee Pages

#### 方式一：Gitee Go 自动同步（推荐）

1. **添加 Gitee 远程仓库**（首次）：
   ```bash
   git remote add gitee https://gitee.com/zgcai/oscanner.git
   ```

2. **推送到 Gitee**：
   ```bash
   git push gitee main
   ```

3. **启用 Gitee Pages**：
   - 进入 Gitee 仓库页面
   - 点击 "服务" → "Gitee Pages"
   - 选择分支：main
   - 部署目录：docs
   - 点击 "启动"

4. **配置自动同步**（可选）：
   - 使用 Gitee Go 配置 GitHub (bjzgcai/oscanner) → Gitee 自动同步
   - 已配置自动同步后，只需推送到 GitHub，Gitee 会自动更新

#### 方式二：手动推送

每次更新后：
```bash
git push origin main  # GitHub
git push gitee main   # Gitee
```

然后在 Gitee Pages 服务中点击 "更新"。

## 项目结构

```
docs/
├── _config.yml           # Jekyll 配置
├── _layouts/             # 页面模板
│   └── default.html
├── assets/               # 静态资源
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   └── main.js
│   └── images/
│       └── hero-bg.png
├── index.html            # 首页
├── Gemfile               # Ruby 依赖
└── README.md             # 本文件
```

## 技术栈

- **静态站点生成器**: Jekyll 4.3
- **样式**: 原生 CSS（无框架依赖）
- **字体**: Inter (Google Fonts)
- **部署**: GitHub Actions + Gitee Pages
- **兼容性**: 现代浏览器

## 注意事项

1. **部署目录**：
   - GitHub Pages 使用 GitHub Actions 自动从 `docs/` 构建
   - Gitee Pages 需要在设置中指定部署目录为 `docs`

2. **baseurl 配置**：
   - 如果使用项目页面（非用户/组织页面），需要在 `_config.yml` 中设置 `baseurl`
   - 当前配置为空，适用于用户/组织页面

3. **更新频率**：
   - GitHub Pages：推送后自动部署
   - Gitee Pages：需要手动点击更新或配置自动同步

## License

Apache License 2.0


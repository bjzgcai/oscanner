# Gitee Pages 部署修复说明

## 问题诊断

部署到 https://zgcai.gitee.io/oscanner/ 后页面未正常显示的原因:

### 根本原因
1. **`baseurl` 配置错误**: 原配置为空字符串 `""`,但 Gitee Pages 部署在子路径 `/oscanner` 下
2. **`url` 配置错误**: 原配置指向 GitHub (`https://bjzgcai.github.io/oscanner`),但实际部署在 Gitee

### 影响
- CSS 文件加载失败: 浏览器尝试从 `https://zgcai.gitee.io/assets/css/style.css` 加载(404)
- JS 文件加载失败: 浏览器尝试从 `https://zgcai.gitee.io/assets/js/main.js` 加载(404)
- 图片资源加载失败: 所有图片路径错误
- 页面显示为无样式的纯 HTML

## 修复内容

### 1. 更新 `pages/_config.yml`

```diff
- baseurl: "" # the subpath of your site, e.g. /blog
- url: "https://bjzgcai.github.io/oscanner"
+ baseurl: "/oscanner" # the subpath of your site, e.g. /blog
+ url: "https://zgcai.gitee.io"
```

### 2. 资源路径验证

所有资源文件已正确放置:
- ✅ `pages/assets/css/style.css` - 主样式表
- ✅ `pages/assets/js/main.js` - 交互脚本
- ✅ `pages/assets/images/hero-bg.png` - Hero 背景图

### 3. 模板验证

`pages/_layouts/default.html` 中使用了正确的 Jekyll 过滤器:
```html
<link rel="stylesheet" href="{{ '/assets/css/style.css' | relative_url }}">
<script src="{{ '/assets/js/main.js' | relative_url }}"></script>
```

`relative_url` 过滤器会自动添加 `baseurl` 前缀,修复后将生成:
- `https://zgcai.gitee.io/oscanner/assets/css/style.css` ✅
- `https://zgcai.gitee.io/oscanner/assets/js/main.js` ✅

## 部署步骤

### 方式一:通过 Gitee 自动部署

1. **提交修复**:
   ```bash
   cd c:\src\gitee\oscanner
   git add pages/_config.yml
   git commit -m "fix: correct baseurl and url for Gitee Pages deployment"
   git push origin main
   ```

2. **触发 Gitee Pages 更新**:
   - 访问 https://gitee.com/zgcai/oscanner/pages
   - 点击"更新"按钮强制重新部署
   - 等待 1-2 分钟让 Gitee Pages 重新构建

3. **验证部署**:
   - 访问 https://zgcai.gitee.io/oscanner/
   - 检查页面样式是否正常显示
   - 打开浏览器开发者工具(F12),确认 Network 标签中没有 404 错误

### 方式二:本地测试(可选)

在推送前本地验证:

```bash
cd c:\src\gitee\oscanner\pages

# 安装 Jekyll(如果未安装)
gem install bundler jekyll

# 安装依赖
bundle install

# 本地运行
bundle exec jekyll serve --baseurl /oscanner

# 访问 http://localhost:4000/oscanner/
```

## 预期结果

修复后,页面应该显示:
- ✅ 专业的渐变 Hero 区域,带背景图
- ✅ 响应式导航栏
- ✅ 功能特性卡片网格
- ✅ 双评估标准标签页(Traditional 6D / AI-Native 2026)
- ✅ 快速开始指南
- ✅ 架构图示
- ✅ 页脚链接
- ✅ 平滑滚动和交互动画

## 兼容性说明

此配置同时兼容 GitHub Pages 和 Gitee Pages:
- **GitHub Pages**: 需要在 `_config.yml` 中设置 `baseurl: "/oscanner"` 和 `url: "https://bjzgcai.github.io"`
- **Gitee Pages**: 当前配置已优化为 `baseurl: "/oscanner"` 和 `url: "https://zgcai.gitee.io"`

如需同时部署到两个平台,建议:
1. 使用 GitHub Actions 自动部署到 GitHub Pages(已配置 `.github/workflows/jekyll.yml`)
2. 手动推送到 Gitee 并在 Gitee Pages 设置中更新

## 故障排查

如果修复后仍有问题:

1. **清除浏览器缓存**: Ctrl+Shift+Delete,清除缓存和 Cookie
2. **检查 Gitee Pages 设置**:
   - 确认部署目录为 `pages`
   - 确认部署分支为 `main` 或 `master`
3. **检查构建日志**: 在 Gitee Pages 设置页面查看构建错误
4. **验证文件权限**: 确保 `pages/` 目录下所有文件可读

## 后续优化建议

1. **添加 favicon**: 在 `pages/assets/images/` 中添加 `favicon.ico`
2. **优化 SEO**: 在 `_config.yml` 中添加更多元数据
3. **添加 Google Analytics**: 如需跟踪访问数据
4. **自动化部署**: 配置 Gitee Go 实现推送后自动更新 Pages

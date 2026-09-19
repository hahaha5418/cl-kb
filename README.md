# CL · 个人 AI 知识库（第二阶段）

用 **VitePress** 搭建，内容是纯 Markdown 文件。改文件 → 提交 → 网站自动更新。

---

## 这一步做了什么升级

| | 第一阶段 | 第二阶段（现在） |
|---|---|---|
| 内容存放 | 塞在 `data.js` 里 | 每个术语 / 任务 / 工具 / 热点都是独立的 `.md` 文件 |
| 加内容 | 要改代码文件 | 在 GitHub 网页上新建文件就行 |
| 页面生成 | 手写 JS 渲染 | 生成器自动出页面、侧边栏、搜索、暗色模式 |
| 搜索 | 简单匹配 | 全站全文搜索 |
| 学习进度 | 存浏览器，换设备就丢 | 写在文件里，跟代码一起备份 |

---

## 部署到 GitHub Pages（约 10 分钟，只做一次）

### 第 1 步：建仓库

1. 登录 <https://github.com>，右上角 `+` → `New repository`
2. **Repository name 填 `ai-kb`**（重要：这个名字要和 `config.mjs` 里的 `base` 对应）
3. 选 **Public**，其他都不勾，点 `Create repository`

### 第 2 步：上传文件（推荐用 GitHub Desktop）

这个项目的源文件有 160 个左右，GitHub 网页一次最多传约 100 个，而且会不小心把 `node_modules` 也传上去。
所以**新手最省事的办法是用官方免费软件 GitHub Desktop**，它能一次性传完、并且自动跳过 `.gitignore` 里的大文件。

1. 下载安装 GitHub Desktop：<https://desktop.github.com>（装完用你的 GitHub 账号登录）
2. 在 github.com 上先把空仓库 `ai-kb` 建好（见第 1 步）
3. 打开 GitHub Desktop → `File` → `Clone repository` → 选 `ai-kb` → 选一个本地位置（比如桌面）→ `Clone`
4. 打开克隆出来的空文件夹，把 `cl-kb` 里的**所有内容**复制进去（包括 `docs/ tools/ scripts/ .github/` 和那几个根文件）
5. 回到 GitHub Desktop，会看到约 160 个待提交文件 → 上方写一句 `init` → 点 `Commit to main` → 再点 `Push origin`（第一次会叫你 `Publish branch`）

> 别担心 `node_modules` 和 `dist`：它们已经被写进 `.gitignore`，GitHub Desktop 会自动跳过，不会传上去。
> 源文件在：`C:\Users\Lenovo\WorkBuddy\2026-09-07-09-57-58\cl-kb`

（如果你坚持用网页上传：进仓库点 `Add file` → `Upload files`，**分批**拖，每次别超过 100 个；而且不要拖 `node_modules` 和 `docs/.vitepress/dist`。）

### 第 3 步：开启 Pages

1. 仓库顶部 `Settings` → 左侧 `Pages`
2. `Source` 选 **GitHub Actions**
3. 回到仓库顶部的 `Actions` 标签，会看到一次自动运行，等它变绿（约 2 分钟）
4. 变绿后回到 `Settings` → `Pages`，顶部会显示你的网址：
   `https://你的用户名.github.io/ai-kb/`

### 第 4 步：改一处用户名

打开 `docs/.vitepress/config.mjs`，把 `你的用户名` 换成你的 GitHub 用户名（保存后每页底部会出现「在 GitHub 上编辑这一页」按钮）。

---

## 以后每天怎么用

打开仓库 → 进 `docs/` → 找到文件 → 点铅笔图标编辑 → 拉到底 `Commit changes` → 等 1-2 分钟，网站自动更新。

**完全不需要在电脑上装任何软件。**

详细说明见网站里的「使用说明」页面，或本地的 `docs/guide.md`。

---

## 第三阶段：每日热点自动更新

### 原理（两个自动流程）

```
每天 UTC 23:00（北京时间早 7:00）
        ↓
  news.yml   → 跑 scripts/fetch_news.py → 抓 RSS → 生成 docs/news/*.md → 自动提交
        ↓
  deploy.yml → 重新生成索引 → 构建网站 → 发布到 GitHub Pages
```

你什么都不用做，早上打开网站就有新内容。

### 已经配置好的 9 个源

OpenAI Blog、Google DeepMind、Hugging Face、TechCrunch AI、The Verge AI、VentureBeat AI、MIT Tech Review、量子位、InfoQ 中文。

实测：单日抓到 35 条，已写入 `docs/news/`。

### 想改什么

| 想改的东西 | 改哪里 |
|---|---|
| 加/删 RSS 源 | `scripts/feeds.json` |
| 每个源每天抓几条 | `feeds.json` 里的 `max_per_feed`（现在 5） |
| 自动抓取的内容保留多久 | `feeds.json` 里的 `keep_days`（现在 60 天） |
| 每天几点抓 | `.github/workflows/news.yml` 里的 `cron`（注意是 UTC，减 8 才是北京时间） |

### 立刻手动跑一次

GitHub 仓库 → `Actions` → 左边点「每日抓取 AI 热点」→ 右上角 `Run workflow` → 绿色按钮。

---

## 为什么不用 n8n / Zapier？

| 方案 | 优点 | 缺点 | 适合谁 |
|---|---|---|---|
| **GitHub Actions**（已实现） | 免费、和网站在一起、不用注册新账号、改起来就是改文件 | 只能定时，不能做复杂判断 | **推荐给你** |
| n8n | 可视化拖拽、能接微信/飞书/邮件推送 | 要自己部署或买云版（约 €20/月起） | 想把新闻推到群里的人 |
| Zapier / Make | 最省事、集成多 | 免费额度很少，中文支持一般 | 已经有账号的人 |

现在的方案已经够用了。等哪天你想「热点来了直接推到微信」，再考虑加 n8n。

---

## 第四阶段：AI 辅助功能（可选 · 没配也能跑）

这个阶段给网站加了「AI 大脑」，但**它是锦上添花，不是必需品**——你没配 API Key，网站照常运行，只是少了 AI 自动生成的那几块。

### AI 帮你做三件事

| 功能 | 命令 | 没配 API Key 时 |
|---|---|---|
| ① 把英文热点翻成中文 + 打标签 | `ai_enrich.py news` | 跳过，热点原样保留 |
| ② 生成「今日学习任务」页 | `ai_enrich.py tasks` | 照常生成，只是没有 AI 那句开场建议 |
| ③ 给笔记自动分类 / 打标签 / 写总结 | `ai_enrich.py notes` | 跳过，笔记原样保留 |

> 你每天打开网站看到的那张「今日学习任务」卡片，就是这里生成的（`docs/today.md`）。

### 怎么开启（一次性，5 分钟）

1. 去一个便宜的大模型平台拿 API Key（推荐 **DeepSeek**，注册送额度，中文也好）：<https://platform.deepseek.com>
2. 打开 GitHub 仓库 → `Settings` → `Secrets and variables` → `Actions` → `New repository secret`
3. **Name** 填 `OPENAI_API_KEY`（注意大小写），**Secret** 填你复制的 Key，保存
4. 回到 `Actions` → 「每日抓取 AI 热点」→ `Run workflow` 跑一次，AI 就会自动给热点翻译、打标签

> 用的是 DeepSeek 兼容 OpenAI 的接口，所以环境变量名字就叫 `OPENAI_API_KEY`。
> 想换成官方 OpenAI / 智谱 / Kimi / 本地 Ollama，改 `scripts/ai_config.json` 的 `base_url` 和 `model` 就行（文件里写了每种的填法）。

### 想调的参数（`scripts/ai_config.json`）

| 参数 | 意思 | 现在的值 |
|---|---|---|
| `daily_task_count` | 每天推几个学习任务 | 3 |
| `note_categories` | 笔记可用的分类（AI 从中选） | 概念理解 / 提示词 / 工具测评 / 项目实践 / 踩坑记录 / 随手记 |
| `batch_size` | 一次喂几条给 AI | 5 |
| `sleep_seconds` | 每次调用间隔，防限流 | 1 |

### 测试一下 API 通不通

```
python scripts/ai_enrich.py check
```

连得通就显示模型返回，连不通会告诉你去哪填 Key。

---

## 常见问题

**Q：想改仓库名？**
可以，但要同时改 `docs/.vitepress/config.mjs` 里的 `base`（比如仓库叫 `cl-kb`，就改成 `base: '/cl-kb/'`）。

**Q：想在自己电脑上预览？**
需要装 Node.js（<https://nodejs.org>，装 LTS 版）。然后在这个文件夹里打开终端，依次运行：

```
npm install
npm run docs:dev
```

浏览器打开 `http://localhost:5173/ai-kb/` 就能看到。这是可选项，不影响日常使用。

**Q：加了新的 `.md` 但侧边栏没出现？**
侧边栏和索引是构建时自动扫描生成的，提交后等 1-2 分钟再刷新。确认文件名以 `.md` 结尾、且不在 `index.md` 上覆盖。

**Q：想换主题色 / 网站名 / 导航项？**
全都在 `docs/.vitepress/config.mjs` 里：

- 网站名：`title: 'CL'`
- 副标题：`description: '...'`
- 顶部导航：`themeConfig.nav: [...]`
- 部署路径：`base: '/ai-kb/'`

要换主题色跟我说一声，我帮你加一个 `custom.css`（要新建两个文件，不复杂但我来写更快）。

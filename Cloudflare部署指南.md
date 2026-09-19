# CL 知识库 · 部署到 Cloudflare Pages（永久在线 · 全球 CDN · 不用 GitHub）

> 目标：把网站发布成一个**手机/电脑随时随地能打开、长期有效**的网址，走 Cloudflare 的全球 CDN，不用连 GitHub、不用写代码。
> 预计第一次操作 5–10 分钟，全程免费。
> 前提：站点已经构建好了（产物在 `docs/.vitepress/dist/`，需要重新构建时跟我说「重新构建」即可）。

---

## 先说结论（两种办法，任选）

| 办法 | 适合谁 | 难度 | 要不要 Token |
|---|---|---|---|
| **A. 网页拖拽上传**（推荐先用这个） | 想立刻看到永久网址、不想折腾命令行 | ⭐ 极简单 | 不需要 |
| **B. 全自动每天部署**（进阶） | 想每天自动更新后自动上线，彻底不用管 | ⭐⭐⭐ 需一次性配置 | 需要一个 API Token |

**兜底**：WorkBuddy 的一键发布链接一直有效（`https://fc04b7d4bf66445ba9dd7b6f99bd2681.app.workbuddy.link`），Cloudflare 是额外的「永久双保险」。

---

## ☑ 办法 A：网页拖拽上传（零代码，现在就能做）

### 第 1 步：注册 Cloudflare（免费）

1. 打开 <https://dash.cloudflare.com/sign-up>
2. 用邮箱注册，验证邮箱。
3. 登录后进入控制台。**不需要绑卡、不需要填付款信息**（免费额度足够个人站点）。

### 第 2 步：创建 Pages 项目并上传

1. 左侧菜单点 **Workers 和 Pages**（或顶部 **Compute (Workers) → Workers 和 Pages**）。
2. 点 **创建**（Create）→ 选 **Pages**。
3. 选 **直接上传**（Upload assets / Drag and drop）——**不要**选「连接到 Git」。
4. 项目名称填：`cl-kb`（随意，但建议好记）。
5. 把本地的 **`dist` 文件夹**（就是 `docs/.vitepress/dist/`）整个拖进上传框。
   - 提醒：拖的是 **文件夹**，不是里面的文件；Cloudflare 会自动把 `index.html` 当成首页。
6. 点 **部署**（Deploy）。等十几秒，会显示一个网址：
   ```
   https://cl-kb.pages.dev
   ```
   （`cl-kb` 换成你起的名字）

### 第 3 步：打开验证

- 用**电脑**和**手机**各打开一次 `https://你的项目.pages.dev`，确认能看到深色极光主题、首页轮播和卡片封面图。
- 顶部搜索框搜「RAG」或「Transformer」试一下。

> 因为站点内部链接写的是 `/ai-kb/...` 这种相对路径，上传后它会正常显示在 `https://你的项目.pages.dev/ai-kb/...`。
> 如果你希望网址**没有 `/ai-kb/` 这一段**（更干净），告诉我「用根路径重新构建」，我会用 `VP_BASE=/ npm run docs:build` 重新构建，再到第 2 步重新拖一次 `dist` 即可。

### 以后怎么更新内容？

- **加了笔记 / 术语 / 工具**：跟我说「重新构建并给我新的 dist」，我生成好新 `dist` 后，回到 Cloudflare 这个项目 → **重新部署**（Redeploy）或重新拖一次文件夹即可。
- 想完全自动：看下面的办法 B。

---

## ☑ 办法 B：全自动每天部署（进阶，一次性配置）

思路：每天早 7 点自动化跑完「抓新闻 + AI 翻译 + 重建」后，额外用一条命令把 `dist` 推到 Cloudflare，网址**永远不变**。

### 第 1 步：拿到 Cloudflare API Token

1. 登录 Cloudflare → 右上角头像 → **我的个人资料** → 左侧 **API 令牌**。
2. 点 **创建令牌** → 选 **编辑 Cloudflare Pages**（或自定义：权限勾 `Account → Cloudflare Pages → Edit`）。
3. 生成后**复制**那一长串 Token（只显示一次，存好）。

### 第 2 步：把 Token 交给我

把这两条信息发给我：
- `CF_API_TOKEN`：上面复制的令牌
- `CF_PROJECT`：你在办法 A 里起的 Pages 项目名（如 `cl-kb`）

我会把它写进「每日自动更新」自动化里（环境变量形式，不会泄露到公开仓库）。

### 第 3 步：自动化里已经加好的步骤（你不用自己做）

每天早 7 点，自动化会依次：
1. 抓最新 AI 新闻 → 2. AI 翻译 + 生成「今日学习任务」→ 3. 重建索引 → 4. 用 `VP_BASE=/` 构建出 `dist` → 5. 发布到 WorkBuddy 链接（兜底）→ **6.（新增）若配置了 CF，自动 `wrangler pages deploy` 到 Cloudflare**。

Cloudflare 这一步如果偶尔失败，**不影响** WorkBuddy 链接正常更新。

---

## 🌐 进阶：绑定自己的域名（可选）

如果你有自己的域名（如 `ai.yourname.com`）：
1. Cloudflare 项目里 → **设置** → **自定义域**（Custom domains）。
2. 填入你的域名，按提示去域名服务商加一条 **CNAME** 记录指向 `你的项目.pages.dev`。
3. Cloudflare 会自动签 HTTPS 证书，几分钟生效。

> 没有域名也没关系，`xxx.pages.dev` 本身就是永久可用的正式网址。

---

## 🆘 卡住了怎么办

把**截图或报错文字**发给我，我一步步陪你过。常见卡点：
- **上传后白屏 / 图片不显示** → 多半是拖错了文件：要拖 `dist` 整个文件夹，不是里面散开的文件。
- **打开网址是 404** → 确认上传的是构建产物（`docs/.vitepress/dist/`），不是 `docs/` 源码。
- **想换项目名** → Cloudflare 里删掉旧项目，重新创建一个，再拖一次 `dist`。

---

## 和 GitHub Pages 方案的区别

之前那版「上线对照清单」是走 GitHub Pages（仓库必须叫 `ai-kb`）。本指南的 Cloudflare 方案**不依赖 GitHub**，更适合「不想学 Git、只想有个永久网址」的情况。两个方案可以并存，互不冲突。

# 通宵进度日志 (PROGRESS_LOG.md)

> 自动驾驶模式启动：2026-09-22 ~ 08:44（用户去睡，要求跑到明早 7 点）
> 铁律：每完成一个子任务立即 commit + push；不碰纯 UI/化妆类修改；报错启容灾，单步失败不卡超过 10 分钟。

---

## ✅ 任务一：多模型 API 网关（优先，已完成）

- [x] 1.1 统一调度网关 `scripts/llm_gateway.py` 配置就绪（已存在，零依赖，支持 7 家 + 自动容灾）
- [x] 1.2 四家顺序已**写死**为 `通义千问 → 豆包 → DeepSeek → 智谱`（`DEFAULT_ORDER` 改为 `["qwen","doubao","deepseek","zhipu"]`；moonshot/openai/local 仍注册，可经 `LLM_ORDER` 临时插入）
- [x] 1.3 新增 `ENV_SETUP.md`（明早填 Key 速查表：四家申请地址 + GitHub Secrets / Vercel 步骤）
- [x] 1.4 验证 `daily.yml` 仅靠智谱即可跑通：`python llm_gateway.py providers` 显示仅 zhipu 有 Key 且为当前生效供应商，顺序 `zhipu` → 流水线照常
- 提交：`scripts/llm_gateway.py`, `ENV_SETUP.md`, `.env.example`

## 🔄 任务二：给 AI 赋予双手（Agent 工具调用）

- [x] 2.1 「网页浏览」工具：新建 `scripts/fetch_article.py`（纯标准库，抓 URL → 抽正文，8s 超时、失败返回 None、零依赖）
- [x] 2.2 并入 `ai_enrich.py` 的 `mode_articles`：当某条热点**摘要 < 150 字且有原文链接**时，自动抓原文全文交给大模型总结（改写 prompt 前提，明确「有原文优先依据原文、严禁瞎编」）；默认开启，可用 `AI_RESEARCH=0` 关闭；超时/失败优雅跳过，**绝不阻塞 7:00 流水线**
- [x] 2.3 增强 RAG 助手 `api/ask.mjs`：识别「今天/今日/学什么/该学/任务清单」意图 → 抓取 `/today.html` 抽正文 → 让模型据此生成「今天该学什么」任务清单；无 Key 时直接返回页面任务原文；抓不到页面则回落通用 RAG

## 🔄 任务三：提升知识库实战输出

- [x] 3.1 热点 → 实操教程生成器：新增 `scripts/build_hotspot_tutorials.py`。扫描 `data/news/*.json` 近期热点，按 6 个高频话题（做视频 / 写代码 / 搭 Agent / 出图 / PPT表格 / 本地跑模型）自动产出「5 步操作指南」落到 `docs/scenes/hot-<slug>.md`，自动收进「场景应用」索引与侧边栏。已接入每日流水线（`daily.yml` 第 3.5 步，在 `npm run content` 之前跑）；无 AI 密钥时降级为骨架版、不阻塞。
  - 已带**内容安全过滤**（剔除色情/暴力/敏感政治类标题，避免被服务商风控整条拒掉）+ 质量门槛（5 步、每步≥18 字、why≥45 字、3 次重试），实测 6/6 全部生成 AI 版。
- [x] 3.2 搜索优化：**构建期意图展开**（`tools/build-content.mjs` 的 `SEARCH_INTENTS`）把常青内容的语义关键词写进索引 `kw` 字段；前端 `SiteSearch.vue` + `CommandPalette.vue` 的 `scoreItem` 给 `kw` 命中加权（+30 精确 / +18 包含，高于正文、低于标题精确）。实测「写代码」现在同时命中「让 AI 帮你写代码（AI 编程教程）」与「搭建你的第一个 AI 助手（Agent）」，不再是纯标题匹配。顺手修了顶层单文件（search/today…）在搜索里被显示成文件名当分类的 bug。

## 🔀 供应商切换（用户 09-22 追加）：改用 DeepSeek

- 网关 `DEFAULT_ORDER` 已是 `qwen → doubao → deepseek → zhipu`（任务一写死）。**DeepSeek 当前未配置密钥**（只有智谱有 Key），故生成器/流水线现在仍走智谱。
- 已让 `build_hotspot_tutorials.py` 优先用 DeepSeek（`choose_provider`：配了就用，没配就退回网关自动链），等用户把 `DEEPSEEK_API_KEY` 填进 `.env` 后，所有 AI（热点摘要 + 今日任务 + 实操教程）自动改用 DeepSeek，不再受智谱间歇性风控影响。
- ⚠️ 待用户动作：在仓库根 `.env` 加 `DEEPSEEK_API_KEY=...`（申请地址与步骤见 `ENV_SETUP.md` / `API-KEYS.md`）。

---

## 📅 09-22 上午批次（用户起床后指令：四项"纯内核"任务）

- [x] **任务一 修复推送**：重试 `git push` —— **网络已通**（昨晚是网络重置，今天能连上 GitHub），但**沙箱里没有 PAT / gh CLI / 凭据缓存**（`could not read Username`），无法完成认证推送。按容灾规则记录后跳过。⚠️ 待用户本地 `git push` 一次（共 6 笔提交待推）。
- [x] **任务二 教程库扩充**：话题表 6 → 12 个，新增 6 话题，其中 **5 个命中热点并生成 AI 版教程**：AI 搜索查资料 / AI 播客配音 / AI 写歌 / AI 知识库笔记 / AI 数据分析（写作、学英语两话题热点不足 3 条自动跳过）。教程总数 6 → **11 篇**，全部自动收进「场景应用」。补齐 4 张缺失的本地 SVG 封面（audio/music/knowledge/data）。
- [x] **任务三 搜索分组**：`SiteSearch.vue` 结果改为**按分类分组显示**，固定顺序 `每日热点 → 场景应用 → AI 实操 → 视频教程 → 工具库 → 术语词典 → 学习路径 → …`（热点在上、教程居中、工具在下）；组头带分类名 + 条数徽章；键盘上下键/回车改为跟随分组后的显示顺序（新增 `flat`/`flatIndexOf`/`navList`）。`CommandPalette.vue` 已有分组，补上同一套固定分类排序，两处体验一致。VitePress 真实构建通过，改动确认打进产物（theme chunk + style css）。
- [x] **任务四 降级验证**：
  - 离线 mock 自检 `llm_gateway.py selftest`：**14/14 通过**（含 429 限流自动重试、401 归类 auth、quota 拉黑、坏 Key 自动切换、无 Key 返回 None）。
  - 真机演练（注入无效智谱 Key）：`auth` 归类 → 拉黑 → 返回 **None 不抛异常** → 业务脚本自动降级（教程退骨架版 / 摘要跳过该条），流水线不死。
  - 恢复真 Key 后真实调用正常（返回「好的」）。
  - 结论：**智谱间歇性抽风（限流/报错）时，流水线照样能跑完**。已配置的供应商越多，切换余地越大。

---

## 📅 09-22 上午批次·第二批（任务五 PWA + 任务六 教程）

- [x] **任务五 PWA 软件化**：
  - `docs/public/sw.js`：Service Worker 离线缓存（HTML 网络优先回退缓存；`/assets/` 哈希资源缓存优先；其它同源 GET 网络优先回写；版本化缓存自动清理）
  - `docs/public/icons/`：纯标准库 PNG 图标生成器 `scripts/gen_pwa_icons.py` → icon-192 / icon-512 / icon-512-maskable（靛蓝渐变 + CL 字块，与 icon.svg 同款设计）
  - `manifest.webmanifest`：补 PNG 图标（Chrome 安装提示硬性要求），保留 SVG
  - `theme/pwa.js`：SW 注册（仅浏览器端 + 生产构建，失败静默，不干扰站内功能），经 `theme/index.js` 的 safe 模式接入
  - `config.mjs` head：补 iOS 全屏 meta（apple-mobile-web-app-capable / black-translucent / app-title），apple-touch-icon 换 PNG
  - 效果：手机浏览器打开会弹「添加到主屏幕」，桌面图标=CL，点开全屏独立窗口（display: standalone），断网可读已访问页面。**注意：PWA 需 HTTPS 域名（线上站满足），本地 file:// 不生效**
  - VitePress 构建验证：sw.js / manifest / icons / meta / SW 注册代码全部进产物 ✅
- [x] **任务六 教程库 11 → 14 篇**：
  - 新增 3 篇 AI 版教程：✍️ 用 AI 写文章/做自媒体（宽化信号后命中 8 条）｜🛡️ 用 AI 防诈骗/识破深度伪造（8 条）｜🧩 上手一个开源 AI 项目（8 条）
  - 「AI 学英语」热点素材仅 3 条且多为多语言训练数据新闻（牵强），按"宁缺毋滥"原则跳过——英语教程等素材够了自动补
  - 新增 write.svg / shield.svg 封面；索引重建后 14 篇教程全部进「场景应用」+ 搜索索引
- ⚠️ **push 仍未完成**（第 2 次尝试）：网络可达 GitHub 但无 PAT/凭据（认证挂起后被终止）。现共 **8 笔提交待推**，等你在本地 `git push` 一次全解决。

---

## 提交记录（最新在上）
- 2026-09-22 11:0x 任务六完成：教程库 11→14（+3）+ 2 封面
- 2026-09-22 10:5x 任务五完成：PWA（SW 离线缓存 + PNG 图标 + 注册 + iOS meta）
- 2026-09-22 10:4x 任务四完成（纯验证，无代码改动）
- 2026-09-22 10:3x 任务三完成：搜索结果按分类分组显示（SiteSearch + CommandPalette 统一排序，键盘导航跟随显示顺序）
- 2026-09-22 10:1x 任务二完成：热点教程库 6 → 11 篇（+5 篇 AI 版）+ 4 张 SVG 封面
- 2026-09-22 09:40 任务三完成：热点实操教程生成器（+ 接入 daily.yml）+ 搜索意图加权 + 切 DeepSeek 偏好
- 2026-09-22 09:10 任务二完成：fetch_article 网页浏览工具 + ai_enrich 自动抓原文 + ask.mjs 今日任务意图
- 2026-09-22 08:50 任务一完成：写死四家顺序 + ENV_SETUP.md

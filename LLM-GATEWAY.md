# 系统架构升级方案 · 从「知识仓库」到「数字大脑」

> 本文档对应三条线的升级：**模型接入层 → Agent 能力层 → 应用层**。
> 第 1 步（模型接入层）**已完成并验证**；第 2、3 步给出已核实过的落地路线。
> 所有改动都不触碰已跑通的抓取 / 日报自动化脚本的对外行为。

---

## 零、总览

| 层 | 目标 | 当前状态 | 关键产物 |
|---|---|---|---|
| 1 模型接入层 | 统一网关，优先通义千问 / 豆包 / DeepSeek，Key 走环境变量 | ✅ **已完成** | `scripts/llm_gateway.py`、`.env.example` |
| 2 Agent 能力层 | 接入 MCP 工具（联网搜索 / 网页浏览），自动检索+总结 | 📋 方案就绪，待决策 | 见第三章 |
| 3 应用层 | 站点 PWA 化（可装到手机桌面）+ Serverless 迁移预研 | 📋 方案就绪，待决策 | 见第四章 |

设计原则：**换模型不改代码、换供应商不断服务、没 Key 也能跑。**

---

## 一、第 1 步：模型接入层（已完成）

### 1.1 架构

```
业务脚本                    统一网关（唯一出入口）              供应商
─────────────              ──────────────────────           ──────────────
ai_enrich.py        ┐                                        通义千问（百炼）
news_library.py     ├──►  Gateway.call() / json()  ──► ① ──► 豆包（火山方舟）
build_tutorials.py  │      · 密钥解析（env 优先）      ② ──► DeepSeek
未来：Agent / API   ┘      · 失败自动切换供应商        ③ ──► 智谱 GLM
                          · 限流退避重试              ④ ──► Kimi / OpenAI / 本地
                          · 用量日志（不含 Key）
```

一个文件：`cl-kb/scripts/llm_gateway.py`（**零依赖**，只用 Python 标准库）。

### 1.2 供应商与优先级

| 优先级 | 键名 | 供应商 | 默认模型 | 环境变量 |
|---|---|---|---|---|
| 1 | `qwen` | 通义千问（阿里云百炼） | `qwen-plus` | `DASHSCOPE_API_KEY` |
| 2 | `doubao` | 豆包（火山方舟 Ark） | `doubao-seed-2-1-pro-260628` | `ARK_API_KEY` |
| 3 | `deepseek` | DeepSeek 深度求索 | `deepseek-chat` | `DEEPSEEK_API_KEY` |
| 4 | `zhipu` | 智谱 GLM（**当前在用**） | `glm-4-flash` | `ZHIPUAI_API_KEY` |
| 5 | `moonshot` | 月之暗面 Kimi | `moonshot-v1-8k` | `MOONSHOT_API_KEY` |
| 6 | `openai` | OpenAI 官方 | `gpt-4o-mini` | `OPENAI_API_KEY` |
| 7 | `local` | 本地模型 Ollama / vLLM | `qwen2.5:7b` | 无需 Key（`OLLAMA_BASE_URL` 启用） |

官方端点（已核实）：
- 通义千问：`https://dashscope.aliyuncs.com/compatible-mode/v1`
- 豆包：`https://ark.cn-beijing.volces.com/api/v3`
- DeepSeek：`https://api.deepseek.com/v1`
- 智谱：`https://open.bigmodel.cn/api/paas/v4`

### 1.3 密钥安全管理

解析优先级（**代码里永不出现 Key**）：

1. 供应商专属环境变量（`DASHSCOPE_API_KEY` 等）
2. 项目根 `cl-kb/.env`（自己解析，无需 python-dotenv）
3. 兼容旧文件 `scripts/ai_config.json`（已 gitignore，会提示迁移）

已核实的 git 忽略状态：

```
.gitignore:17:.env*                    → .env 被忽略 ✅
.gitignore:19:!.env.example            → .env.example 可入库 ✅（模板，不含真实 Key）
.gitignore:22:logs/                    → 用量日志不入库 ✅
.gitignore:14:scripts/ai_config.json   → 旧明文配置不入库 ✅
```

**模型名单独覆盖**（账号可用模型与默认值不一致时用，互不影响）：

| 变量 | 作用 |
|---|---|
| `QWEN_MODEL` / `DOUBAO_MODEL` / `DEEPSEEK_MODEL` / `ZHIPU_MODEL` | 只改这一家的模型名 |
| `LLM_MODEL` | 全局强制（所有家都用这一个，通常只在单供应商场景用） |

优先级：单家专属变量 → `LLM_MODEL` → 旧配置 → 内置默认值。
例：豆包报 404 时，把 `DOUBAO_MODEL` 设成控制台里已开通的模型名或 `ep-` 接入点 ID 即可。

**key 申请与配置的完整图文步骤见 [`API-KEYS.md`](./API-KEYS.md)。**

### 1.4 容灾机制（自动，无需配置）

| 情况 | 网关行为 |
|---|---|
| Key 无效（401/403） | 标记该家本轮不可用 → **自动换下一家** |
| 余额不足 / 免费额度用尽 | 同上（`quota`） |
| 模型未开通（豆包常见 404） | 同上（`notfound`） |
| 触发限流（429） | **指数退避重试**（默认 2 次）→ 仍失败才切换 |
| 网络超时 / 不可达 | 重试 → 切换 |
| 一家都没配 | **全站 AI 优雅降级**：脚本照常跑完，只是没有 AI 增强 |

### 1.5 三步启用（给非技术用户）

```bash
cd cl-kb
copy .env.example .env          # 复制模板
# 用记事本打开 .env，把申请到的 Key 填在等号右边（有几个填几个）
python scripts/llm_gateway.py providers     # 看识别状态
python scripts/llm_gateway.py check          # 真实连通测试
```

把现有智谱 Key 从明文文件迁走：

```bash
python scripts/llm_gateway.py migrate          # 预演，只显示不写入
python scripts/llm_gateway.py migrate --write  # 写入 .env
```

### 1.6 CLI 诊断命令

| 命令 | 用途 |
|---|---|
| `providers` | 表格查看 7 家供应商 + 密钥配置状态 + 当前生效链路 |
| `check [--provider qwen]` | 逐个真实调用测试连通性 |
| `failover` | **真机演练**：故意让首选供应商的 Key 失效，验证是否自动切到下一家 |
| `env` | 查看 `.env` 加载情况与可见的环境变量（值已脱敏） |
| `chat "问题"` / `json "..."` | 命令行直接对话 / 测 JSON 输出 |
| `selftest` | **离线自测**（本地 mock，不联网、不消耗额度） |
| `migrate [--write]` | 明文配置 → `.env` 迁移 |

### 1.7 业务代码怎么用（新旧写法都支持）

```python
# 老写法（现有脚本，一行都不用改）
from ai_enrich import AI
ai = AI(cfg)                       # cfg 可来自 ai_config.json，传 {} 也可以
text = ai.call("把这段英文翻成中文：...")
data = ai.json("输出 JSON：{'要点': [...]}")

# 新写法（推荐，指定供应商 / 多轮 / 流式）
from llm_gateway import Gateway
gw = Gateway()
gw.chat([{"role": "system", "content": "你是编辑"},
         {"role": "user", "content": "写一条热点摘要"}])                 # 自动选可用供应商
gw.chat("同一句话", provider="deepseek")                                  # 指定供应商
gw.chat("写长文", model="qwen-max")                                       # 指定模型
for piece in gw.chat_stream("讲一个故事"):  print(piece, end="")           # 流式
print(gw.enabled, gw.provider_name, gw.model)                            # 状态自检
```

### 1.8 已验证结果（本次实测）

| 验证项 | 结果 |
|---|---|
| 离线自测（mock） | **14 通过 / 0 失败** —— 覆盖基础调用、JSON 围栏解析、429 退避重试、DashScope 原生返回结构、401/欠费分类与黑名单、**坏供应商→好供应商自动切换**、SSE 流式、无 Key 降级 |
| 真实连通 | 智谱 `glm-4-flash` **0.55s 返回「正常」** |
| 旧接口兼容 | `ai_enrich.py check` → `OK`（走网关，行为不变） |
| 下游导入 | `ai_enrich` / `news_library` / `build_tutorials` 三个脚本的 `AI` 均正确解析到 `llm_gateway.Gateway`，`CONFIG_FILE` 契约保留 |
| 密钥安全 | `.env` 被忽略、`.env.example` 可入库、Key 在 CLI 中一律脱敏显示（`3a650b****FT2A`） |

### 1.9 日志

每次调用追加一行到 `cl-kb/logs/llm-calls.jsonl`（已 gitignore）：

```json
{"ts":"2026-09-21T19:55:00+0800","provider":"zhipu","model":"glm-4-flash",
 "ok":true,"kind":"ok","seconds":0.55,"prompt_tokens":9,"completion_tokens":2}
```

只记供应商 / 模型 / token / 耗时，**不记录 Key、不记录提示词正文**。可用于后续做成本归因。

---

## 二、现有业务接入点（受影响范围）

| 脚本 | 用到的能力 | 改动 |
|---|---|---|
| `scripts/ai_enrich.py` | 热点中文化、站内富文本、今日学习任务、笔记打标签 | 内置类 → 改为 `from llm_gateway import AI`，**业务逻辑零改动** |
| `scripts/news_library.py` | 12 字段热点详情库生成 | 无需改动（经 `ai_enrich` 间接使用） |
| `scripts/build_tutorials.py` | 教程生成 | 无需改动 |

每日 9:00 自动化的调用命令、参数、输出文件**完全不变**，因此升级不影响已跑通的内容流水线。

---

## 三、第 2 步：Agent 能力层（方案，待启动）

**目标**：让 AI 能调用「联网搜索」和「网页浏览」，完成自动信息检索与总结。

**关键判断：不需要先引入一整个 Agent 框架，就能拿到这个能力。** 按成本从低到高，建议分三阶段：

### 阶段 2a（推荐先做）：用模型厂商原生的联网工具

豆包（火山方舟）已提供带 `web_search` 工具的 Responses API，**一次请求即可完成"搜索 + 阅读 + 总结"**，无需自己抓网页：

```python
# POST https://ark.cn-beijing.volces.com/api/v3/responses
{
  "model": "doubao-seed-2-1-pro-260628",
  "tools": [{"type": "web_search"}],
  "input": [{"role": "user", "content": "总结今天 AI 领域最重要的 3 条新闻"}]
}
```

- 接入方式：在 `llm_gateway.py` 增加一个 `web_search()` 方法（复用现有密钥解析与错误分类），**网关继续做唯一出入口**。
- 存量收益：现有 `fetch_news.py` 只吃 RSS，有了联网搜索后，可以让 AI 主动去找 RSS 覆盖不到的源，并自动补全"详细摘要 / 原文摘录"字段。
- 备选：阿里云百炼的 MCP 广场同样提供联网搜索 / 浏览器类 MCP 服务。

### 阶段 2b：引入长期记忆层（Cognee）

- **Cognee**（Apache 2.0，GitHub 3 万+ star）：图谱 + 向量 + 关系型混合存储，四个动作 `remember / recall / forget / improve`，本地用 SQLite + LanceDB + Kuzu 即可跑，自带 **MCP server**（可被 Claude Code / Cursor 等直接调用）。
- 适合本站点的用法：把 508 条热点详情库、术语库、学习路径灌进去，让 AI 助手能"跨天检索 + 关联推理"（例如："这条新闻和我上周学的术语有什么关系"）。
- **不选它当工具调用层**：它是记忆底座，不负责联网浏览；工具调用交给 2a 或 MCP。

### 阶段 2c：参考 OpenAgents 的工程范式（不直接照搬）

Open Agents 的价值在于把三件事做成样板：durable workflow（长任务可恢复）、控制逻辑与沙箱执行分离、Git 交付链路内建。对本站点而言，**现阶段只需要吸收"可恢复"这一条**——即抓取/生成任务失败后可续跑，而不是重建一套 Agent 运行时。

### 决策点
1. 是否申请豆包 Key（火山方舟需在控制台**逐个开通**模型，否则报 404）？
2. 联网搜索的产出，是自动写进「每日热点详情库」，还是先只做人工触发的「深度调研」功能？

---

## 四、第 3 步：应用层（方案，待启动）

### 3.1 PWA 化（可安装到手机桌面）

VitePress 是纯静态站，PWA 改造只需四个动作：

1. `docs/public/manifest.webmanifest` —— 应用名、图标、`display: standalone`、主题色（沿用深空蓝 `#05070f`）
2. `docs/public/sw.js` —— Service Worker：
   - `assets/*`（带 hash，内容不变）→ **cache-first**
   - `*.html` / `news-library.json` → **network-first**（保证每天新内容不被旧缓存挡住）
   - 提供离线兜底页
3. 图标集：192 / 512 / maskable，复用现有封面生成脚本 `scripts/gen_covers.py` 的思路生成
4. `config.mjs` 的 `head` 里注入 `<link rel="manifest">` 与 SW 注册脚本

**注意事项**（都是真实坑）：
- PWA 要求 **HTTPS**（线上满足；`localhost` 也算安全上下文，本地可测）
- Service Worker 一旦上线，**缓存策略错了会让用户看不到新内容**——这正是每日更新的站点最怕的，所以 HTML 必须 network-first
- iOS Safari 走"添加到主屏幕"，Android Chrome 会弹安装提示

### 3.2 Serverless 迁移预研（阿里云 AgentRun）

**AgentRun = 函数计算 FC 上的 Agent 运行时**，特点（已核实官方文档）：

- Serverless，零运维、自动扩缩容、按量付费；**解决长任务超时**问题
- 内置百炼模型接入（默认 `qwen-plus`），也支持自定义模型 → **与我们第 1 步的网关天然对齐**
- 内置工具：**浏览器（联网搜索 / 浏览网页）**、代码解释器、数据库连接器、自定义 API
- 模型高可用：**自动熔断 + 多模型 Fallback**（与网关的容错策略同构）
- 部署方式：`npm i -g @serverless-devs/s` → `s init agentrun-quick-start-langchain` → 配 `AGENTRUN_ACCESS_KEY_ID / _SECRET / _ACCOUNT_ID / _REGION` 环境变量 → 部署
- 产出：`https://xxx.agentrun.aliyuncs.com/agent/<id>` + 调用凭证，支持**流式返回**

**迁移路径建议（三阶段，先易后难）**

| 阶段 | 做什么 | 收益 |
|---|---|---|
| 1 | 把"每日内容生成流水线"（news → 详情库）搬上去，由定时触发 | 摆脱本地机器在线依赖 |
| 2 | 把 AI 助手改为调用云上 Agent 端点（前端只换一个 URL） | 手机端也能用，响应更快 |
| 3 | 多 Agent 协同（搜索 Agent → 分析 Agent → 报告 Agent，A2A 协议） | 自动化深度调研 |

**关键前置条件**：需要一个阿里云账号，并开通「函数计算 FC + AgentRun + 百炼」三项服务。**这一步涉及你的账号与付费，需要你确认后才能进行。**

### 决策点
1. PWA 先做，还是先做 Serverless？（建议 **PWA 先做**：零成本、当天见效、不依赖任何云账号）
2. 是否已有阿里云账号并接受按量付费？

---

## 五、下一步（等你拍板）

- **A. 立即启用多供应商容灾**：申请通义千问 / 豆包 Key 填进 `.env`，从"单点智谱"升级为"三线容灾"（5 分钟）
- **B. 启动第 2 步阶段 2a**：网关加 `web_search()`，让热点自动补齐 RSS 覆盖不到的内容
- **C. 启动第 3 步 PWA**：站点可装到手机桌面（当天可验证）
- **D. 三方并行**：我做 B 和 C，你同时去申请 Key 和确认阿里云账号

---

*第 1 步代码：`cl-kb/scripts/llm_gateway.py`（约 1100 行，零依赖）· 配置模板：`cl-kb/.env.example`*

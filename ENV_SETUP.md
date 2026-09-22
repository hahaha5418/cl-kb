# ENV_SETUP.md —— 明天早上起来填 Key 的速查表

> 目标：把 **通义千问 → 豆包 → DeepSeek → 智谱** 四家模型全部接进统一网关（代码已写好，只差填 Key）。
> 配 1 家就能跑，配 2 家以上自动获得**故障切换**：一家挂了另一家顶上，流水线不中断。
> 更详细的逐家图文指引见同仓库 [`API-KEYS.md`](./API-KEYS.md)。

---

## 一、四个要填的变量（先记住这四个名字）

| 顺序 | 平台 | 环境变量名（**一字不差**） | 申请地址 |
|---|---|---|---|
| 1 | **通义千问**（阿里云百炼） | `DASHSCOPE_API_KEY` | https://bailian.console.aliyun.com/ |
| 2 | **豆包**（火山方舟） | `ARK_API_KEY` | https://console.volcengine.com/ark |
| 3 | **DeepSeek** | `DEEPSEEK_API_KEY` | https://platform.deepseek.com/api_keys |
| 4 | **智谱 GLM**（你现在已在用的免费那家） | `ZHIPU_API_KEY` | https://open.bigmodel.cn/usercenter/apikeys |

> ⚠️ 变量名必须全大写、下划线、拼写正确，否则网关认不到 = 白填。
> 智谱你已经有一把 `ZHIPU_API_KEY` 在本地 `.env` 里，所以现在管线**只用智谱就能跑通**，先别慌。

---

## 二、申请 Key 的三句话版（详细版看 API-KEYS.md）

1. **通义千问**：打开上面地址 → 支付宝/淘宝扫码登录 → 做**实名认证**（领免费额度的前提）→ 头像 → API-KEY 管理 → 创建并**立刻复制**（`sk-` 开头）。
2. **豆包**：打开上面地址 → 注册火山引擎 → 做**实名认证** → 左侧「开通管理」**一键开通所有模型**（不开通会报 404）→ API Key 管理 → 创建并复制（`ark-` 开头）。
3. **DeepSeek**：打开上面地址 → 注册 → API keys → 创建 → 复制 `sk-` 开头；**它没免费额度，需充值（最低 ¥1）**，不充也不影响（网关自动跳过这一家）。
4. **智谱**：打开上面地址 → 注册 → 创建 API Key → 复制（免费，`glm-4-flash`）。

---

## 三、把 Key 填进这三个地方（按你用到的填）

### 📍 A. 本机运行（最快验证，建议先做）
```bash
cd C:/Users/Lenovo/WorkBuddy/2026-09-07-09-57-58/cl-kb
copy .env.example .env
```
用记事本打开 `cl-kb/.env`，把四个变量的值填在 `=` 右边（**只填你有的**，没有的整行留着别删），保存。
验证：
```bash
C:/Users/Lenovo/.workbuddy/binaries/python/versions/3.13.12/python.exe scripts/llm_gateway.py providers
```
看到 `✅ 可用` 就成功。`.env` 已被 `.gitignore` 忽略，**不会**进 GitHub。

### 📍 B. GitHub Secrets（让每天 07:00 的自动更新用上 —— 这是你最该填的）
1. 打开 https://github.com/hahaha5418/cl-kb
2. **Settings** → 左侧 **Secrets and variables** → **Actions**
3. 点 **New repository secret**，按下面名字逐个加（Name 必须完全一致，Value 粘你的 Key）：

   | Name | Value |
   |---|---|
   | `DASHSCOPE_API_KEY` | 千问 Key |
   | `ARK_API_KEY` | 豆包 Key |
   | `DEEPSEEK_API_KEY` | DeepSeek Key |
   | `ZHIPU_API_KEY` | 智谱 Key |

4. **不用改任何代码** —— `daily.yml` 已写好引用。加完可到 **Actions** 页面点 **Run workflow** 手动验证一次。
   > 只加了一部分也完全 OK：没配的那家自动跳过，不报错。

### 📍 C. Vercel 环境变量（让网页右下角「AI 助手」用上，海外主站）
`api/ask.mjs` 已支持这四家容灾。
1. https://vercel.com/dashboard → 选中 cl-kb 项目 → **Settings** → **Environment Variables**
2. 逐个 **Add New**，填 `DASHSCOPE_API_KEY` / `ARK_API_KEY` / `DEEPSEEK_API_KEY` / `ZHIPU_API_KEY`（都选 Production/Preview/Development），再加一个 `VP_BASE` = `/`
3. ⚠️ 改完必须 **Redeploy** 才生效（Deployments → 最新一条 → ⋯ → Redeploy）。

---

## 四、填好后怎么验收

告诉我「**填好了**」，我会在这台机器跑这三条并把结果贴给你：
```bash
scripts/llm_gateway.py providers   # 看哪几家亮了
scripts/llm_gateway.py check       # 逐家真实连通测试
scripts/llm_gateway.py failover    # 故意让首选失效，验证自动切换
```
预期：`4/4 供应商可用` + 切换演练显示「✅ 切换成功」。

---

## 五、安全底线
- Key 只放 `.env` 和平台环境变量里，**绝不**写进代码 / 聊天 / 截图。
- 万一泄露：去对应控制台**删旧 Key 建新 Key**，旧 Key 立刻失效，不用改代码。
- 本地 `.env` 已被 git 忽略；入库的 `.env.example` 是模板（**没有真 Key**），别往里填真值。

# API Key 申请指引 —— 四家全接

> 目标：把 **通义千问 → 豆包 → DeepSeek → 智谱** 四家全部接进统一网关。
> 配 1 家能跑，配 2 家以上自动获得**故障切换**能力（一家挂了另一家顶上）。
> 四家全配 ≈ 30 分钟，其中大部分时间是在等实名认证。

---

## 一、总览（先看这张表）

| 顺序 | 平台 | 要填的变量名 | 申请地址 | 花钱吗 |
|---|---|---|---|---|
| 1 | **通义千问**（阿里云百炼） | `DASHSCOPE_API_KEY` | https://bailian.console.aliyun.com/ | 新用户送免费额度，够用很久 |
| 2 | **豆包**（火山方舟） | `ARK_API_KEY` | https://console.volcengine.com/ark | 有免费额度，开通模型本身不收费 |
| 3 | **DeepSeek** | `DEEPSEEK_API_KEY` | https://platform.deepseek.com/api_keys | 需充值，最低 ¥1 起，很便宜 |
| 4 | **智谱 GLM** | `ZHIPUAI_API_KEY` | https://open.bigmodel.cn/usercenter/apikeys | `glm-4-flash` 免费（你现在用的就是它）|

> 💡 变量名必须**一字不差**（全大写、下划线）。填错名字 = 网关认不到 = 白填。

---

## 二、逐家申请（照着点）

### 1️⃣ 通义千问（主力推荐，中文强、国内直连）

1. 打开 https://bailian.console.aliyun.com/
2. 用**支付宝 / 淘宝 / 钉钉**扫码登录（没有阿里云账号就顺手注册，30 秒）
3. **完成实名认证** —— 点右上角头像 → 实名认证 → 用支付宝扫脸，约 1 分钟
   （这是领免费额度的前置条件，不做的话没额度）
4. 首次进入会弹服务协议，**点同意即自动开通百炼**（开通本身不收费）
5. 右上角头像 → **API-KEY 管理** → **创建 API-KEY** → 归属选「主账号」→ 确定
6. **立刻复制**（`sk-` 开头，**只完整显示这一次**，关掉弹窗就再也看不到）
7. 顺手进「权益 / 额度管理」页：确认免费额度到账，并**开启「免费额度用完即停」**
   （防止额度耗尽后自动转为扣费）

**要填的变量**：
```
DASHSCOPE_API_KEY=sk-你复制的那一串
```

---

### 2️⃣ 豆包（火山方舟 Ark）

1. 打开 https://console.volcengine.com/ark
2. 手机号注册火山引擎账号 → **完成个人实名认证**（身份证 + 人脸，约 5 分钟）
3. **关键一步**：左侧菜单 → **「开通管理」** → 点击**「一键开通所有模型」**
   ⚠️ 不开通直接调用会报 **404 模型不存在**，这一步不能跳
   （开通只是给使用权限，不产生费用）
4. 左侧菜单 → **「API Key 管理」** → **创建 API Key** → **立刻复制**（`ark-` 开头）

**要填的变量**：
```
ARK_API_KEY=ark-你复制的那一串
```

**如果之后报 404 / 模型不存在**（不同账号能用的模型名不一样）：
去「开通管理」里看你**实际已开通**的模型名，然后单独为豆包指定：
```
DOUBAO_MODEL=你已开通的模型名
```
也可以填「推理接入点 ID」（`ep-` 开头，在「在线推理 → 接入点」里创建后能看到）。
> `DOUBAO_MODEL` 只影响豆包，不会动到千问/DeepSeek/智谱。

---

### 3️⃣ DeepSeek

1. 打开 https://platform.deepseek.com/api_keys
2. 注册 / 登录（支持手机号 + 微信扫码）
3. 左侧 **「API keys」** → **「创建新 API Key」** → 复制 `sk-` 开头的串
4. 左侧 **「充值 / Billing」** 充一笔（**最低 ¥1 起**，支付宝/微信）

**要填的变量**：
```
DEEPSEEK_API_KEY=sk-你复制的那一串
```

> ⚠️ DeepSeek **没有免费额度**，余额为 0 时会返回 **402**。
> 不过不用怕：网关遇到 402 会自动跳到下一家，业务不会中断。
> 也就是说 **不充值也不影响你，只是这一家不参与**。

---

### 4️⃣ 智谱 GLM（你现在已在用的免费那家）

1. 打开 https://open.bigmodel.cn/usercenter/apikeys
2. 注册 / 登录（手机号）
3. **创建 API Key** → 复制

**要填的变量**：
```
ZHIPUAI_API_KEY=你复制的那一串
```

> 这家是站点当班模型 `glm-4-flash`（免费），建议保留作为最后一道兜底。

---

## 三、填到哪里（三个地方，按需选）

### 📍 场景 A：本机运行（建议先做这个，最快见效）

```bash
cd C:/Users/Lenovo/WorkBuddy/2026-09-07-09-57-58/cl-kb
copy .env.example .env
```

然后用记事本打开 `cl-kb/.env`，把上面 4 行的值填在等号右边（**只填你有的**，没有的整行留着不管），保存。

**验证**（填完立刻能看结果）：
```bash
cd C:/Users/Lenovo/WorkBuddy/2026-09-07-09-57-58/cl-kb
C:/Users/Lenovo/.workbuddy/binaries/python/versions/3.13.12/python.exe scripts/llm_gateway.py providers
```
看到 `✅ 可用` 就成功了。

> 🔒 `.env` 已被 `.gitignore` 忽略，**永远不会被提交到 GitHub**，可以放心放 Key。
> 反过来：`.env.example` 是模板（没有真 Key），它是入库的，**不要往里面填真 Key**。

---

### 📍 场景 B：GitHub Secrets（让每天 07:00 的自动更新用上）

1. 打开 https://github.com/hahaha5418/cl-kb
2. **Settings** → 左侧 **Secrets and variables** → **Actions**
3. 点右侧绿色按钮 **New repository secret**
4. 依次添加 4 个（**Name 必须和下面完全一致**，Value 粘贴你的 Key）：

   | Name | Value |
   |---|---|
   | `DASHSCOPE_API_KEY` | 你的千问 Key |
   | `ARK_API_KEY` | 你的豆包 Key |
   | `DEEPSEEK_API_KEY` | 你的 DeepSeek Key |
   | `ZHIPU_API_KEY` | 你的智谱 Key（注意这里workspace里用的是这个旧名字，两个都会被识别）|

5. **不需要改任何代码** —— 工作流 `daily.yml` 里已经写好了引用，加完即生效。
   加完可以到 **Actions** 页面点 **Run workflow** 手动跑一次验证。

> 只加了一部分也没关系：没配的那家会自动跳过，不会报错。

---

### 📍 场景 C：Vercel 环境变量（让网页里的 AI 助手用上）

`api/ask.mjs`（网页右下角「AI 助手」的后端）已同步支持这四家容灾。

1. 打开 https://vercel.com/dashboard → 选中你的项目（cl-kb）
2. 顶部 **Settings** → 左侧 **Environment Variables**
3. 逐个 **Add New**，填入下表（**4 个 Key + 1 个 VP_BASE**）：

   | Key | Value | Environment |
   |---|---|---|
   | `DASHSCOPE_API_KEY` | 你的千问 Key | Production / Preview / Development 全勾 |
   | `ARK_API_KEY` | 你的豆包 Key | 同上 |
   | `DEEPSEEK_API_KEY` | 你的 DeepSeek Key | 同上 |
   | `ZHIPU_API_KEY` | 你的智谱 Key | 同上 |
   | `VP_BASE` | `/` | 同上 |

4. ⚠️ **改完必须 Redeploy 才生效**：Deployments → 最新一条 → 右侧 `⋯` → **Redeploy**

---

## 四、填好之后

跟我说一句「**填好了**」，我会立刻在这台机器上跑下面三条命令并把结果给你看：

```bash
# ① 看识别状态（哪些家已点亮）
python scripts/llm_gateway.py providers

# ② 逐家真实连通测试（每家发一句"请只回复两个字：正常"）
python scripts/llm_gateway.py check

# ③ 真机故障切换演练（故意让首选那家失效，看是否自动切到下一家）
python scripts/llm_gateway.py failover
```

**预期结果**：`④/④ 个供应商可用` + 切换演练显示
`✅ 切换成功：通义千问 被判定不可用 → 「豆包」自动接管`。

---

## 五、常见坑（提前避开）

| 现象 | 原因 | 怎么办 |
|---|---|---|
| `providers` 里显示「未配置」 | 变量名拼错 / `.env` 没保存成 `.env`（存成了 `.env.txt`） | 检查文件名和大小写 |
| 千问报 401 或没有免费额度 | 没做实名认证 | 去阿里云补实名认证 |
| 豆包报 **404 模型不存在** | 模型没在控制台开通，或模型名不适用你的账号 | 执行「一键开通所有模型」，必要时用 `DOUBAO_MODEL=` 指定 |
| DeepSeek 报 **402** | 余额为 0 | 充 ¥1，或干脆不配这家（网关会自动跳过） |
| 四家全填了但只用了一家 | 正常的——**优先级高的先用**，这就是设计 | 想看切换就跑去 `failover` 命令 |
| Vercel 改了变量但没反应 | 没 Redeploy | 手动 Redeploy 一次 |

> 🔐 安全提醒：Key 只放在 `.env` 和平台的环境变量里。**永远不要**粘进代码文件、聊天记录或截图里。
> 万一泄露：去对应控制台**删除旧 Key 并重建**，旧 Key 立刻失效，不用改代码，只要更新环境变量里的值。

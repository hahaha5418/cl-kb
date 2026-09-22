// api/ask.mjs  —— Vercel Serverless Function (Node.js)
// 专属 AI 助手（RAG）：读取构建期生成的 kb-index.json，检索相关片段，
// 再调用大模型基于资料作答。密钥只在服务端使用，绝不暴露给前端。
//
// 多模型容灾：按「通义千问 → 豆包 → DeepSeek → 智谱」顺序尝试，
// 某家 Key 失效 / 欠费 / 模型未开通 → 自动切下一家，用户无感。
// 与本地 Python 端 scripts/llm_gateway.py 的优先级保持一致。
//
// 部署前提：在 Vercel 项目 Environment Variables 里配置至少一个 Key
//   DASHSCOPE_API_KEY / ARK_API_KEY / DEEPSEEK_API_KEY / ZHIPU_API_KEY
//   （配几个用几个，配 2 个以上即获得自动切换能力）
//   VP_BASE = /   （与站点 base 保持一致）
//
// 可选高级开关：
//   LLM_ORDER=deepseek,zhipu     自定义尝试顺序
//   QWEN_MODEL / DOUBAO_MODEL / DEEPSEEK_MODEL / ZHIPU_MODEL   单独指定模型

const PROVIDERS = [
  {
    name: 'qwen',
    label: '通义千问',
    url: 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
    envs: ['DASHSCOPE_API_KEY', 'QWEN_API_KEY', 'TONGYI_API_KEY'],
    model: 'qwen-plus',
  },
  {
    name: 'doubao',
    label: '豆包',
    url: 'https://ark.cn-beijing.volces.com/api/v3/chat/completions',
    envs: ['ARK_API_KEY', 'DOUBAO_API_KEY', 'VOLC_API_KEY'],
    model: 'doubao-seed-2-1-pro-260628',
  },
  {
    name: 'deepseek',
    label: 'DeepSeek',
    url: 'https://api.deepseek.com/v1/chat/completions',
    envs: ['DEEPSEEK_API_KEY'],
    model: 'deepseek-chat',
  },
  {
    name: 'zhipu',
    label: '智谱 GLM',
    url: 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
    envs: ['ZHIPUAI_API_KEY', 'ZHIPU_API_KEY', 'GLM_API_KEY'],
    model: 'glm-4-flash',
  },
]

// 这些错误重试没意义，直接换下一家：401 鉴权 / 402 欠费 / 403 / 404 模型未开通
const FATAL_STATUS = new Set([401, 402, 403, 404])

function firstKey(p) {
  for (const e of p.envs) {
    const v = (process.env[e] || '').trim()
    if (v) return v
  }
  return ''
}

function modelOf(p) {
  return (process.env[p.name.toUpperCase() + '_MODEL'] || '').trim() || p.model
}

// 按优先级筛出「配了 Key」的供应商
function chain() {
  const forced = (process.env.LLM_ORDER || '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
  const list = forced.length
    ? forced.map((n) => PROVIDERS.find((p) => p.name === n)).filter(Boolean)
    : PROVIDERS
  return list
    .map((p) => ({ ...p, key: firstKey(p), model: modelOf(p) }))
    .filter((p) => p.key)
}

function readBody(req) {
  return new Promise((resolve) => {
    let data = ''
    req.on('data', (c) => (data += c))
    req.on('end', () => resolve(data))
  })
}

function tokenize(s) {
  const out = new Set()
  ;(s.toLowerCase().match(/[a-z0-9]{2,}/g) || []).forEach((w) => out.add(w))
  const zh = s.replace(/[^一-龥]/g, '')
  if (zh.length === 1) out.add(zh)
  for (let i = 0; i < zh.length - 1; i++) out.add(zh.slice(i, i + 2))
  return [...out]
}

function score(text, grams) {
  if (!text) return 0
  const t = text.toLowerCase()
  let s = 0
  for (const g of grams) if (t.includes(g)) s += g.length >= 2 ? 2 : 1
  return s
}

// 同实例缓存：10 分钟内只下载一次索引
let _cache = null
let _cacheAt = 0
async function loadIndex(origin) {
  const now = Date.now()
  if (_cache && now - _cacheAt < 10 * 60 * 1000) return _cache
  const r = await fetch(origin + '/kb-index.json')
  _cache = (await r.json()).chunks || []
  _cacheAt = now
  return _cache
}

// 抓取首页「今日学习任务」页面（/today.html），抽成纯文本，用于回答「今天我该学什么」
async function fetchToday(origin) {
  try {
    const r = await fetch(origin + '/today.html', { signal: AbortSignal.timeout(8000) })
    if (!r.ok) return null
    const html = await r.text()
    let t = html.replace(/<(script|style|noscript)[^>]*>[\s\S]*?<\/(script|style|noscript)>/gi, ' ')
    t = t.replace(/<[^>]+>/g, ' ')
    t = t.replace(/\s+/g, ' ').trim()
    return t.length > 120 ? t.slice(0, 2400) : null
  } catch {
    return null
  }
}

// 单家调用。成功返回文本；失败抛错并带上 status（便于判断是否该换家）
async function askOne(p, system, user) {
  const resp = await fetch(p.url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${p.key}` },
    body: JSON.stringify({
      model: p.model,
      temperature: 0.3,
      messages: [
        { role: 'system', content: system },
        { role: 'user', content: user },
      ],
    }),
    signal: AbortSignal.timeout(45000),
  })
  if (!resp.ok) {
    const brief = (await resp.text().catch(() => '')).slice(0, 200)
    const err = new Error(`${p.label} 返回 ${resp.status} ${brief}`)
    err.status = resp.status
    throw err
  }
  const data = await resp.json()
  const answer = data?.choices?.[0]?.message?.content
  if (!answer) throw new Error(`${p.label} 未返回内容`)
  return answer
}

// 依次尝试，返回 { answer, provider }；全失败返回 { error }
async function askWithFailover(system, user) {
  const list = chain()
  if (!list.length) {
    return {
      error:
        '服务端尚未配置任何模型 Key，请先在部署平台添加环境变量：' +
        'DASHSCOPE_API_KEY / ARK_API_KEY / DEEPSEEK_API_KEY / ZHIPU_API_KEY（任一个即可）。',
      status: 503,
    }
  }
  let last = null
  for (let i = 0; i < list.length; i++) {
    const p = list[i]
    const tries = 2 // 网络抖动 / 限流允许重试 1 次
    for (let attempt = 1; attempt <= tries; attempt++) {
      try {
        const answer = await askOne(p, system, user)
        return { answer, provider: p.label, model: p.model, switched: i > 0 }
      } catch (e) {
        last = e
        const fatal =
          FATAL_STATUS.has(e.status) ||
          e.name === 'AbortError' ||
          /未返回内容/.test(e.message)
        if (fatal) break // 换下一家，不再重试这一家
        if (attempt < tries) await new Promise((r) => setTimeout(r, 400 * attempt))
      }
    }
  }
  return { error: '所有已配置的模型都调用失败：' + (last ? last.message : '未知原因'), status: 502 }
}

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*')
  res.setHeader('Access-Control-Allow-Methods', 'POST,OPTIONS')
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type')
  if (req.method === 'OPTIONS') return res.status(204).end()
  if (req.method !== 'POST') return res.status(405).end('Method Not Allowed')

  const raw = await readBody(req)
  let q = ''
  try {
    q = (JSON.parse(raw || '{}').q || '').trim()
  } catch {
    q = raw.toString().trim()
  }
  if (!q) return res.status(400).json({ error: '问题不能为空' })

  // 取知识库索引（构建期生成，放在 public/ 下，随站点一起部署）
  // 同实例 10 分钟内只拉一次，避免每次请求都下载整份索引
  const origin = process.env.VERCEL_URL
    ? `https://${process.env.VERCEL_URL}`
    : process.env.SITE_URL || 'http://localhost:3000'
  let chunks = []
  try {
    chunks = await loadIndex(origin)
  } catch (e) {
    return res.status(502).json({ error: '知识库索引加载失败：' + e.message })
  }

  // 意图：今天该学什么 / 今日任务 / 学习计划 → 直接读「今日学习任务」页面作答
  const isToday = /今天|今日|今天该学|今天.*(学|任务|做)|学什么|该学|任务清单|学习计划|今天学/.test(q)
  if (isToday) {
    const tctx = await fetchToday(origin)
    if (tctx) {
      const system =
        '你是“CL 的 AI 知识库”专属助手。下面是从“今日学习任务”页面提取出的内容，' +
        '请用简体中文、分点、口语化地告诉用户：今天建议学什么、做哪几件事，并鼓励他们动手。' +
        '只能依据页面内容，不要编造页面里没有的任务；没有模型可用于生成时，直接把页面里的任务列给用户也行。'
      const user = `【今日学习任务页面内容】\n${tctx}\n\n【问题】${q}`
      const r = await askWithFailover(system, user)
      if (r.answer) {
        return res.status(200).json({
          answer: r.answer,
          refs: [],
          provider: r.provider,
          model: r.model,
          switched: r.switched,
        })
      }
      // 没有配任何模型 Key：直接把页面里的任务原文返给用户
      return res.status(200).json({
        answer: '今天的学习任务如下（页面原文）：\n' + tctx.slice(0, 1400),
        refs: [],
      })
    }
    // 抓不到今日页面则回落到下面的通用 RAG
  }

  // 检索：n-gram 命中打分，取前 5 段
  const grams = tokenize(q)
  const top = chunks
    .map((c) => ({ c, s: score(c.text + ' ' + c.title, grams) }))
    .filter((x) => x.s > 0)
    .sort((a, b) => b.s - a.s)
    .slice(0, 5)
  const ctx = top.map((x) => `【${x.c.title}】\n${x.c.text}`).join('\n\n').slice(0, 3600)

  const system =
    '你是“CL 的 AI 知识库”专属助手。只能依据下面【资料】回答，用简体中文、分点、通俗地作答；' +
    '若资料里没有相关信息，请明确说“资料里没有提到这一点”，不要编造。'
  const user = ctx ? `【资料】\n${ctx}\n\n【问题】${q}` : q

  const r = await askWithFailover(system, user)
  if (r.error) return res.status(r.status || 502).json({ error: r.error })

  return res.status(200).json({
    answer: r.answer,
    refs: top.map((x) => ({ title: x.c.title, url: x.c.url })),
    // 便于排查是哪家在干活（前端可以忽略这两个字段）
    provider: r.provider,
    model: r.model,
    switched: r.switched,
  })
}

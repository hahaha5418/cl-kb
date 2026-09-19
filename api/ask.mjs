// api/ask.mjs  —— Vercel Serverless Function (Node.js)
// 专属 AI 助手（RAG）：读取构建期生成的 kb-index.json，检索相关片段，
// 再调用智谱 GLM-4-Flash 基于资料作答。密钥只在服务端使用，绝不暴露给前端。
//
// 部署前提：在 Vercel 项目 Environment Variables 里配置
//   ZHIPU_API_KEY = 你的智谱 API Key
//   VP_BASE       = /          （与站点 base 保持一致）

const ZHIPU_URL = 'https://open.bigmodel.cn/api/paas/v4/chat/completions'

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

  const KEY = process.env.ZHIPU_API_KEY
  if (!KEY) {
    return res.status(503).json({ error: '服务端尚未配置 ZHIPU_API_KEY，请先在部署平台添加环境变量。' })
  }

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

  try {
    const r = await fetch(ZHIPU_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${KEY}` },
      body: JSON.stringify({
        model: 'glm-4-flash',
        temperature: 0.3,
        messages: [
          { role: 'system', content: system },
          { role: 'user', content: user },
        ],
      }),
    })
    const data = await r.json()
    const answer = data?.choices?.[0]?.message?.content || '（模型未返回内容）'
    return res.status(200).json({
      answer,
      refs: top.map((x) => ({ title: x.c.title, url: x.c.url })),
    })
  } catch (e) {
    return res.status(502).json({ error: '调用大模型失败：' + e.message })
  }
}

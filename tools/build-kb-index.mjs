// tools/build-kb-index.mjs
// 构建期生成「站内知识库索引」docs/public/kb-index.json
// 供 P4 的 RAG 悬浮窗（api/ask.mjs）做检索上下文。
// 用法：node tools/build-kb-index.mjs   （已并入 package.json 的 content 脚本）

import fs from 'node:fs'
import path from 'node:path'

const DOCS = path.resolve('docs')
const OUT = path.resolve(DOCS, 'public/kb-index.json')
const BASE = (process.env.VP_BASE || '/').replace(/\/+$/, '') || '/'

function walk(dir, out = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (e.name === '.vitepress' || e.name === 'node_modules' || e.name === 'public') continue
    if (e.name.startsWith('_')) continue
    const p = path.join(dir, e.name)
    if (e.isDirectory()) walk(p, out)
    else if (e.name.endsWith('.md')) out.push(p)
  }
  return out
}

function readFM(src) {
  const m = src.match(/^---\n([\s\S]*?)\n---/)
  if (!m) return { title: '', body: src }
  const fm = {}
  for (const line of m[1].split('\n')) {
    const mm = line.match(/^([\w-]+):\s*(.*)$/)
    if (mm) fm[mm[1]] = mm[2].replace(/^["']|["']$/g, '').trim()
  }
  return { title: fm.title || '', body: src.slice(m[0].length) }
}

// 去掉 markdown / HTML 噪声，保留可读文本（保留连字符和下划线，避免破坏 text-align、glm-4-flash 等词）
function clean(t) {
  return t
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`[^`]*`/g, ' ')
    .replace(/<[^>]+>/g, ' ') // 去掉 HTML 标签
    .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ')
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/^\s{0,3}#{1,6}\s+/gm, ' ') // 标题 #
    .replace(/^\s{0,3}>+\s?/gm, ' ') // 引用 >
    .replace(/\s+/g, ' ')
    .trim()
}

// 纯 UI 页（404 / 搜索）不进知识库，避免噪声
const SKIP = new Set(['404', 'search'])

function urlFor(file) {
  let rel = path.relative(DOCS, file).replace(/\\/g, '/').replace(/\.md$/, '')
  if (rel === 'index') rel = ''
  return (BASE + '/' + rel).replace(/\/+/g, '/')
}

function chunk(file) {
  const base = path.basename(file, '.md')
  if (SKIP.has(base)) return []
  const { title, body } = readFM(fs.readFileSync(file, 'utf8'))
  const text = clean(body)
  if (!text) return []
  const docTitle = title || base
  // 按二级标题切分；没有小标题则整篇作为一个 chunk
  const parts = body.split(/^##\s+/m).filter(Boolean)
  if (parts.length <= 1) {
    return [{ title: docTitle, text: text.slice(0, 900), url: urlFor(file) }]
  }
  return parts.slice(1).map((p) => {
    const head = p.split('\n', 1)[0].trim()
    const t = clean(p)
    return { title: head ? `${docTitle} · ${head}` : docTitle, text: t.slice(0, 700), url: urlFor(file) }
  })
}

const files = walk(DOCS)
const chunks = files.flatMap(chunk).filter((c) => c.text.length > 12)

fs.mkdirSync(path.dirname(OUT), { recursive: true })
fs.writeFileSync(OUT, JSON.stringify({ generatedAt: new Date().toISOString(), count: chunks.length, chunks }), 'utf8')
console.log(`[kb-index] ${chunks.length} 个知识片段 -> ${path.relative(process.cwd(), OUT)}`)

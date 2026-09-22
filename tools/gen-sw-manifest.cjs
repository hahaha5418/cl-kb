#!/usr/bin/env node
/* 生成 Service Worker 的分层离线缓存清单（sw-manifest.json）。
 *
 * 用法：node tools/gen-sw-manifest.cjs <dist目录>
 *   例：node tools/gen-sw-manifest.cjs docs/.vitepress/dist
 *
 * 在 vitepress build 之后运行：扫描产物目录，输出带优先级分层的文件清单，
 * SW 在用户首次打开后按层在后台分批缓存，实现「打开一次，全站离线可用」：
 *
 *   t1  应用外壳：带哈希的 JS/CSS、字体、JSON 数据、图标、manifest
 *       （所有页面都依赖它们，必须最先缓存）
 *   t2  全部非新闻内容页：教程 / 路径 / 术语 / 工具 / 场景 / 指南 …
 *       （知识库的「正文」，断网飞机上的主要阅读对象）
 *   t3  新闻热点页：按日期从新到旧排列，SW 只自动预缓存最近
 *       NEWS_PRECACHE 篇，其余「访问一次即永久缓存」
 *
 * 忽略：清单自身 / SW 自身 / robots / sourcemap / 超 8MB 单文件。
 */
const fs = require('fs')
const path = require('path')

const dist = path.resolve(process.argv[2] || path.join(__dirname, '..', 'docs', '.vitepress', 'dist'))
if (!fs.existsSync(dist)) {
  console.error('gen-sw-manifest: 目录不存在 ' + dist)
  process.exit(1)
}

const IGNORE = new Set(['sw-manifest.json', 'sw.js', 'robots.txt'])
const IGNORE_EXT = new Set(['.map', '.txt'])
const MAX_BYTES = 8 * 1024 * 1024

const T1_EXT = new Set(['.js', '.css', '.woff2', '.woff', '.json', '.webmanifest', '.png', '.svg', '.xml'])

const entries = []
  ; (function walk(dir) {
    for (const name of fs.readdirSync(dir)) {
      if (name.startsWith('.')) continue
      const fp = path.join(dir, name)
      const st = fs.statSync(fp)
      if (st.isDirectory()) { walk(fp); continue }
      if (IGNORE.has(name) || IGNORE_EXT.has(path.extname(name))) continue
      if (st.size > MAX_BYTES) continue
      const url = '/' + path.relative(dist, fp).split(path.sep).join('/')
      const rel = url.slice(1)
      const ext = path.extname(name)
      let tier
      if (ext === '.html') {
        tier = rel.startsWith('news/') ? 3 : 2
      } else if (T1_EXT.has(ext)) {
        tier = 1
      } else {
        continue // 未知类型不预缓存（走运行时缓存兜底）
      }
      entries.push({ u: url, s: st.size, t: tier })
    }
  })(dist)

/* t3（新闻）按日期从新到旧；其余按层级+路径稳定排序 */
entries.sort((a, b) => {
  if (a.t !== b.t) return a.t - b.t
  if (a.t === 3) return b.u.localeCompare(a.u) // 新闻：新的在前
  return a.u.localeCompare(b.u)
})

const bytes = entries.reduce((s, e) => s + e.s, 0)
const out = { v: 1, generatedAt: new Date().toISOString(), total: entries.length, bytes, files: entries }
fs.writeFileSync(path.join(dist, 'sw-manifest.json'), JSON.stringify(out), 'utf8')
const byTier = [1, 2, 3].map((t) => `t${t}:${entries.filter((e) => e.t === t).length}`).join(' ')
console.log(`SW 清单：${entries.length} 个文件 / ${(bytes / 1048576).toFixed(1)}MB（${byTier}）→ dist/sw-manifest.json`)

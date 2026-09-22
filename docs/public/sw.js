/* CL 知识库 Service Worker v2 —— 全站离线可用
 *
 * 目标：打开一次，整个知识库（含全部教程）断网也能完整翻阅。
 *
 * 分层后台预缓存（由构建脚本 tools/gen-sw-manifest.cjs 生成清单）：
 *   t1 应用外壳：JS/CSS/字体/JSON 数据/图标 —— 所有页面依赖，最先缓存
 *   t2 全部非新闻内容页：教程/路径/术语/工具/场景/指南 —— 飞机上的主要读物
 *   t3 新闻热点页：自动预缓存最近 NEWS_PRECACHE 篇，其余访问一次即永久缓存
 *
 * 运行时策略：
 *   - 页面导航：网络优先，失败回退缓存（保证在线时内容最新）
 *   - /assets/ 带哈希产物：缓存优先（内容永不变，命中即秒开）
 *   - 其它同源 GET：网络优先 + 后台写缓存（访问过 = 离线可读）
 *
 * 消息接口（postMessage 到 SW）：
 *   {type:'PRECACHE_STATUS'} → 回 {type:'PRECACHE_STATUS', done, total, cachedAll}
 *   {type:'PRECACHE_ALL'}    → 立即开始缓存清单里剩余全部文件（含所有历史热点）
 */
const CACHE_NAME = 'cl-kb-v2'
const MANIFEST_URL = '/sw-manifest.json'
const NEWS_PRECACHE = 60          // 自动预缓存的最新热点篇数（其余访问即缓存）
const CONCURRENCY = 4             // 后台缓存并发数（对手机流量/电量友好）
const CORE_URLS = ['/', '/manifest.webmanifest', '/icons/icon-192.png', '/icons/icon-512.png']

let precacheDone = 0
let precacheTotal = 0

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => Promise.allSettled(CORE_URLS.map((u) => cache.add(new Request(u, { cache: 'reload' })))))
      .then(() => self.skipWaiting())
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys()
      await Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
      // 请求持久化存储：降低浏览器在磁盘紧张时清掉我们离线包的概率
      try { if (self.navigator.storage && self.navigator.storage.persist) await self.navigator.storage.persist() } catch (_) {}
      await self.clients.claim()
      backgroundPrecache() // 不 await：后台慢慢下，不打断用户
    })()
  )
})

/* ---------- 后台分层预缓存 ---------- */
let precacheRunning = false

async function backgroundPrecache(all = false) {
  if (precacheRunning) return
  precacheRunning = true
  try {
    const res = await fetch(MANIFEST_URL, { cache: 'reload' })
    if (!res || !res.ok) return
    const manifest = await res.json()
    const cache = await caches.open(CACHE_NAME)
    const already = await cache.keys()
    const have = new Set(already.map((r) => new URL(r.url).pathname))

    // 分层取队列：t1 全取、t2 全取、t3 取最近 NEWS_PRECACHE（all=true 时全取）
    const queue = []
    for (const f of manifest.files || []) {
      if (f.t <= 2 || all || f.t === 3) {
        if (f.t === 3 && !all) {
          // t3 只取清单里排最前（最新）的 NEWS_PRECACHE 篇
          const newsIdx = queue.filter((x) => x.t === 3).length
          if (newsIdx >= NEWS_PRECACHE) continue
        }
        queue.push(f)
      }
    }
    precacheTotal = queue.length
    precacheDone = 0

    // 分批并发：逐个检查缓存里有没有，没有才下载
    let batch = []
    for (const f of queue) {
      batch.push(f)
      if (batch.length >= CONCURRENCY) {
        await cacheBatch(cache, batch.splice(0), have)
      }
    }
    if (batch.length) await cacheBatch(cache, batch, have)
  } catch (_) {
    // 清单拉取失败（旧部署/断网）→ 静默放弃，运行时缓存兜底
  } finally {
    precacheRunning = false
  }
}

async function cacheBatch(cache, batch, have) {
  await Promise.all(batch.map(async (f) => {
    if (have.has(f.u)) { precacheDone++; return }
    try {
      await cache.add(new Request(f.u, { cache: 'reload' }))
      have.add(f.u)
    } catch (_) { /* 单个失败不影响整体 */ }
    precacheDone++
  }))
}

/* ---------- 消息接口 ---------- */
self.addEventListener('message', (event) => {
  const msg = event.data || {}
  if (msg.type === 'PRECACHE_STATUS') {
    event.source && event.source.postMessage({
      type: 'PRECACHE_STATUS',
      done: precacheDone,
      total: precacheTotal,
      running: precacheRunning,
    })
  } else if (msg.type === 'PRECACHE_ALL') {
    backgroundPrecache(true)
  }
})

/* ---------- 运行时缓存策略 ---------- */
self.addEventListener('fetch', (event) => {
  const req = event.request
  if (req.method !== 'GET') return

  const url = new URL(req.url)
  if (url.origin !== self.location.origin) return // 跨域（外链/统计）直接走网络

  // 1) 页面导航：网络优先，断网回退缓存（缓存过一次 = 离线永久可读）
  if (req.mode === 'navigate' || (req.headers.get('accept') || '').includes('text/html')) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone()
          caches.open(CACHE_NAME).then((c) => c.put(req, copy)).catch(() => {})
          return res
        })
        .catch(() =>
          caches.match(req, { ignoreSearch: true }).then((hit) => hit || caches.match('/'))
        )
    )
    return
  }

  // 2) 带哈希的构建产物：缓存优先
  if (url.pathname.startsWith('/assets/')) {
    event.respondWith(
      caches.match(req).then(
        (hit) =>
          hit ||
          fetch(req).then((res) => {
            const copy = res.clone()
            caches.open(CACHE_NAME).then((c) => c.put(req, copy)).catch(() => {})
            return res
          })
      )
    )
    return
  }

  // 3) 其它同源 GET（图片/JSON 等）：网络优先 + 回写缓存
  event.respondWith(
    fetch(req)
      .then((res) => {
        if (res && res.status === 200 && res.type === 'basic') {
          const copy = res.clone()
          caches.open(CACHE_NAME).then((c) => c.put(req, copy)).catch(() => {})
        }
        return res
      })
      .catch(() => caches.match(req))
  )
})

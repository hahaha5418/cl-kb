/* ============================================================
   TimeAgo · 把 <span class="cl-time" data-ts="..."> 渲染成
   「X 分钟前更新」，并在页面停留时自动刷新
   ------------------------------------------------------------
   为什么需要它：站点是静态的，"X 分钟前" 在构建那一刻就固定了。
   这段脚本让时间差在浏览器里实时计算，用户什么时候打开都是准的。
   ============================================================ */

function fmt(diff) {
  if (diff < 60) return '刚刚更新'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前更新`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前更新`
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)} 天前更新`
  if (diff < 86400 * 30) return `${Math.floor(diff / 86400 / 7)} 周前更新`
  return null // 太久了，交给下面的日期兜底
}

export function updateTimeAgo() {
  if (typeof document === 'undefined') return
  const nodes = document.querySelectorAll('.cl-time[data-ts]')
  nodes.forEach((el) => {
    const raw = el.getAttribute('data-ts')
    if (!raw) return
    const t = new Date(raw)
    if (isNaN(t.getTime())) return
    const diff = Math.max(0, (Date.now() - t.getTime()) / 1000)
    const text = fmt(diff)
    if (text) {
      el.textContent = '🕒 ' + text
    } else {
      const p = (n) => String(n).padStart(2, '0')
      el.textContent = `🕒 ${t.getFullYear()}-${p(t.getMonth() + 1)}-${p(t.getDate())}`
    }
  })
}

export function installTimeAgo() {
  if (typeof window === 'undefined') return
  updateTimeAgo()

  // 每 30 秒刷新一次时间差
  setInterval(updateTimeAgo, 30000)

  // 站内是 SPA 路由，换页后新内容也要重新计算
  if (typeof MutationObserver !== 'undefined') {
    let timer = null
    const mo = new MutationObserver(() => {
      clearTimeout(timer)
      timer = setTimeout(updateTimeAgo, 60)
    })
    mo.observe(document.body, { childList: true, subtree: true })
  }
}

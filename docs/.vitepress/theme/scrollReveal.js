/* ============================================================
   滚动出现动画 + 顶部阅读进度条（纯前端，零依赖，不联网）
   - 不支持 JS 时：所有内容默认可见，不会变空白
   - 用户设置了「减少动态效果」时：直接全显示，不做动画
   ============================================================ */

export function installScrollReveal() {
  if (typeof document === 'undefined') return
  if (typeof window === 'undefined') return

  const reduce =
    window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  if (reduce) return

  // 需要入场动画的元素：卡片、板块 hero、首页 banner、三步区、文章小标题、以及手动标记的
  const selector =
    '.cl-card, .cl-hero-grad, .cl-banner, .cl-step, .cl-steps, .cl-callout, .cl-bili, .vp-doc h2, .vp-doc h3, [data-reveal]'
  const targets = document.querySelectorAll(selector)
  if (!targets.length) return

  // 给 <html> 打标记：只有 JS 正常时才隐藏初始态，避免无 JS 时空白
  document.documentElement.classList.add('js-reveal-ready')

  targets.forEach((el) => {
    el.classList.add('cl-reveal')
    // 同屏内的兄弟元素做轻微错峰，更有层次感
    const sibs = Array.from(el.parentElement ? el.parentElement.children : [])
    const idx = sibs.indexOf(el)
    el.style.setProperty('--rd', (idx % 8) * 55 + 'ms')
  })

  if (!('IntersectionObserver' in window)) {
    targets.forEach((el) => el.classList.add('in'))
  } else {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add('in')
            io.unobserve(e.target)
          }
        })
      },
      { threshold: 0.12, rootMargin: '0px 0px -8% 0px' }
    )
    targets.forEach((el) => io.observe(el))
  }

  // —— 顶部阅读进度条（细渐变线）——
  const bar = document.createElement('div')
  bar.className = 'cl-progress'
  bar.setAttribute('aria-hidden', 'true')
  document.body.appendChild(bar)

  let ticking = false
  const update = () => {
    const h = document.documentElement
    const max = h.scrollHeight - h.clientHeight
    const pct = max > 0 ? (h.scrollTop || document.body.scrollTop) / max : 0
    bar.style.transform = 'scaleX(' + Math.min(1, Math.max(0, pct)) + ')'
    ticking = false
  }
  const onScroll = () => {
    if (!ticking) {
      ticking = true
      window.requestAnimationFrame(update)
    }
  }
  window.addEventListener('scroll', onScroll, { passive: true })
  window.addEventListener('resize', onScroll, { passive: true })
  update()
}

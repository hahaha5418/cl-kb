// 赛博朋克微交互 · 纯前端
// 1) 卡片 3D 悬浮倾斜 + 放大（鼠标经过）
// 2) 点击卡片 / 按钮时的霓虹发光波纹（click glow）
// 不破坏现有结构：只对 .cl-card / .cl-tool-panel / .cl-callout 等已有类生效。

export function installMicroInteractions() {
  if (typeof document === 'undefined') return
  const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches

  const tiltTargets = document.querySelectorAll('.cl-card, .cl-tool-panel, .cl-callout')
  tiltTargets.forEach((el) => {
    el.style.transformStyle = 'preserve-3d'
    el.style.willChange = 'transform'

    if (!reduce) {
      el.addEventListener('mousemove', (e) => {
        const r = el.getBoundingClientRect()
        const px = (e.clientX - r.left) / r.width - 0.5
        const py = (e.clientY - r.top) / r.height - 0.5
        el.style.transform =
          `perspective(900px) rotateX(${(-py * 7).toFixed(2)}deg) ` +
          `rotateY(${(px * 9).toFixed(2)}deg) translateY(-6px) scale(1.03)`
      })
      el.addEventListener('mouseleave', () => {
        el.style.transform = ''
      })
    }
    // 点击发光波纹
    el.addEventListener('click', (e) => spawnGlow(el, e))
  })

  // 搜索结果项也加发光
  document.querySelectorAll('.cl-search-item').forEach((el) => {
    el.addEventListener('click', (e) => spawnGlow(el, e))
  })
}

function spawnGlow(el, e) {
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
  const r = el.getBoundingClientRect()
  const x = (e && e.clientX ? e.clientX - r.left : r.width / 2)
  const y = (e && e.clientY ? e.clientY - r.top : r.height / 2)
  const span = document.createElement('span')
  span.className = 'cl-glow-ripple'
  span.style.left = x + 'px'
  span.style.top = y + 'px'
  el.appendChild(span)
  span.addEventListener('animationend', () => span.remove())
  // 兜底清理
  setTimeout(() => span.remove(), 900)
}

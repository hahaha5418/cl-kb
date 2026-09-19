/* ============================================================
   文章内图片灯箱（纯前端，零依赖，不联网）
   - 点击 .vp-doc 里的任意图片 → 全屏放大查看
   - 再点一下 / 按 Esc 关闭
   - 不支持 JS 时：图片照常显示，只是不能放大，不影响阅读
   ============================================================ */

export function installLightbox() {
  if (typeof document === 'undefined') return
  if (typeof window === 'undefined') return
  // 用户若设置了「减少动态效果」，就不启用放大弹层
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return

  const overlay = document.createElement('div')
  overlay.className = 'cl-lightbox'
  overlay.setAttribute('aria-hidden', 'true')
  overlay.innerHTML = '<img class="cl-lightbox-img" alt="">'
  document.body.appendChild(overlay)

  const img = overlay.querySelector('img')
  const open = (src, alt) => {
    img.src = src
    img.alt = alt || ''
    overlay.classList.add('open')
    document.body.style.overflow = 'hidden'
  }
  const close = () => {
    overlay.classList.remove('open')
    img.src = ''
    document.body.style.overflow = ''
  }

  overlay.addEventListener('click', close)
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') close()
  })

  // 只接管文章正文里的图片，不碰卡片封面 / hero 装饰图
  document.addEventListener('click', (e) => {
    const t = e.target
    if (t && t.tagName === 'IMG' && t.closest('.vp-doc')) {
      const src = t.currentSrc || t.src
      if (src) {
        e.preventDefault()
        open(src, t.alt)
      }
    }
  })
}

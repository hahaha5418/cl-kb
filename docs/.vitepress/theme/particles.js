// 赛博朋克粒子动态背景 · 纯前端零外网
// 在 <body> 上注入一张固定 canvas（#cl-particles）做霓虹粒子+连线，
// 再叠一层极淡的科技网格（.cl-cyber-grid）。尊重 prefers-reduced-motion，
// 不依赖任何接口，不连数据库，绝不会 404。

export function installParticles() {
  if (typeof document === 'undefined') return
  // 全页导航每次都重新执行 setup → 用幂等守卫避免重复注入
  if (document.getElementById('cl-particles')) return

  const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches

  // 1) 科技网格底纹
  const grid = document.createElement('div')
  grid.className = 'cl-cyber-grid'
  document.body.appendChild(grid)

  // 2) 粒子 canvas
  const canvas = document.createElement('canvas')
  canvas.id = 'cl-particles'
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  canvas.width = Math.floor(window.innerWidth * dpr)
  canvas.height = Math.floor(window.innerHeight * dpr)
  document.body.appendChild(canvas)

  const ctx = canvas.getContext('2d')
  const W = () => window.innerWidth
  const H = () => window.innerHeight

  const COLORS = ['#00f0ff', '#b026ff', '#ff2bd6', '#7c3aed']
  // 首页粒子密一点，其它页少一点（靠 body 上的标记判断）
  const isHome = document.body.classList.contains('cl-home') || !!document.querySelector('.cl-banner')
  const COUNT = reduce ? 0 : (isHome ? 70 : 42)

  let pts = []
  function seed() {
    pts = []
    for (let i = 0; i < COUNT; i++) {
      pts.push({
        x: Math.random() * W(),
        y: Math.random() * H(),
        vx: (Math.random() - 0.5) * 0.35,
        vy: (Math.random() - 0.5) * 0.35,
        r: Math.random() * 1.8 + 0.8,
        c: COLORS[(Math.random() * COLORS.length) | 0]
      })
    }
  }
  seed()

  function resize() {
    canvas.width = Math.floor(W() * dpr)
    canvas.height = Math.floor(H() * dpr)
  }
  window.addEventListener('resize', resize)

  function frame() {
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, W(), H())
    const linkDist = 130
    for (let i = 0; i < pts.length; i++) {
      const p = pts[i]
      p.x += p.vx; p.y += p.vy
      if (p.x < 0 || p.x > W()) p.vx *= -1
      if (p.y < 0 || p.y > H()) p.vy *= -1
      // 点
      ctx.beginPath()
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
      ctx.fillStyle = p.c
      ctx.globalAlpha = 0.85
      ctx.fill()
      // 连线
      for (let j = i + 1; j < pts.length; j++) {
        const q = pts[j]
        const dx = p.x - q.x, dy = p.y - q.y
        const d = Math.hypot(dx, dy)
        if (d < linkDist) {
          ctx.globalAlpha = (1 - d / linkDist) * 0.22
          ctx.strokeStyle = p.c
          ctx.lineWidth = 0.6
          ctx.beginPath()
          ctx.moveTo(p.x, p.y)
          ctx.lineTo(q.x, q.y)
          ctx.stroke()
        }
      }
    }
    ctx.globalAlpha = 1
    if (!reduce) requestAnimationFrame(frame)
  }

  if (reduce) {
    // 静态画一帧即可（无动画，省电）
    frame()
  } else {
    requestAnimationFrame(frame)
  }
}

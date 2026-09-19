// 赛博朋克 AI 虚拟伴侣 / 吉祥物 · 纯前端
// 左下角浮动一个霓虹光环头像，点击展开引导气泡，气泡里轮播使用提示。
// 无任何外部接口，不连数据库，绝不会 404。

const TIPS = [
  '嗨～我是你的 AI 向导 CL。点任意卡片，会有霓虹发光特效哦 ✨',
  '想快速找内容？按键盘 <kbd>/</kbd> 或点首页搜索条，站内全搜 🔍',
  '「时光引擎」帮你规划昨天 / 今天 / 明天，碎片时间也能进步 ⏳',
  '「技能树」像打游戏一样点亮进度，学完一关就亮一格 🌟',
  '看到的视频都是 B站嵌入，不用下载，点开即看 📺',
  '你的学习进度存在浏览器本地，刷新不丢，换设备才需要重新记 💾'
]

export function installMascot() {
  if (typeof document === 'undefined') return
  if (document.getElementById('cl-mascot')) return

  const wrap = document.createElement('div')
  wrap.className = 'cl-mascot'
  wrap.id = 'cl-mascot'
  wrap.innerHTML = `
    <div class="cl-mascot-bubble" id="cl-mascot-bubble" role="status" aria-live="polite">
      <span class="cl-mascot-tip"></span>
    </div>
    <button class="cl-mascot-avatar" id="cl-mascot-avatar" aria-label="打开 AI 向导提示" title="我是你的 AI 向导">🤖</button>
  `
  document.body.appendChild(wrap)

  const avatar = wrap.querySelector('#cl-mascot-avatar')
  const bubble = wrap.querySelector('#cl-mascot-bubble')
  const tipEl = wrap.querySelector('.cl-mascot-tip')

  let idx = 0
  let timer = null
  const showTip = (i) => { tipEl.innerHTML = TIPS[i % TIPS.length] }
  showTip(0)

  const open = () => {
    bubble.hidden = false
    idx = (idx + 1) % TIPS.length
    showTip(idx)
    timer = setInterval(() => { idx = (idx + 1) % TIPS.length; showTip(idx) }, 5200)
  }
  const close = () => {
    bubble.hidden = true
    clearInterval(timer)
  }
  avatar.addEventListener('click', () => {
    if (bubble.hidden) open()
    else close()
  })

  // 进场 1.4s 后自动冒泡一次，提示用户
  setTimeout(() => { if (bubble.hidden) open() }, 1400)
  // 8 秒后自动收起，不打扰
  setTimeout(() => { if (!bubble.hidden) close() }, 1400 + 8000)
}

// 阅读体验闭环（纯前端，仅在浏览器端运行）：
//   - 右下角「复制本页链接」浮动按钮：点一下把当前地址复制到剪贴板（或调用系统分享），
//     方便用户把某一篇术语 / 工具 / 热点转发给朋友。不依赖任何后端。
export function installReadingEnhancements() {
  if (document.querySelector('.cl-sharefab')) return

  const fab = document.createElement('button')
  fab.type = 'button'
  fab.className = 'cl-sharefab'
  fab.setAttribute('aria-label', '复制本页链接')
  fab.title = '复制本页链接'
  fab.textContent = '🔗'
  fab.addEventListener('click', async () => {
    const url = location.href
    try {
      if (navigator.share) {
        await navigator.share({ title: document.title, url })
        return
      }
      await navigator.clipboard.writeText(url)
      toast('链接已复制，去分享吧 🔗')
    } catch (e) {
      toast('复制失败，请手动复制地址栏链接')
    }
  })
  document.body.appendChild(fab)

  let toastEl
  function toast(msg) {
    if (!toastEl) {
      toastEl = document.createElement('div')
      toastEl.className = 'cl-toast'
      document.body.appendChild(toastEl)
    }
    toastEl.textContent = msg
    toastEl.classList.add('show')
    clearTimeout(toastEl._t)
    toastEl._t = setTimeout(() => toastEl.classList.remove('show'), 1800)
  }
}

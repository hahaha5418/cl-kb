import DefaultTheme from 'vitepress/theme'
import { h } from 'vue'
import './style.css'
import HomeBanner from './components/HomeBanner.vue'
import VideoEmbed from './components/VideoEmbed.vue'
import SiteFooter from './components/SiteFooter.vue'
import BiliEmbed from './components/BiliEmbed.vue'
import Step from './components/Step.vue'
import Steps from './components/Steps.vue'
import Callout from './components/Callout.vue'
import SiteSearch from './components/SiteSearch.vue'
import MiniTools from './components/MiniTools.vue'
import NewsLibrary from './components/NewsLibrary.vue'
import ProgressCheck from './components/ProgressCheck.vue'
import HomeProgress from './components/HomeProgress.vue'
import RelatedLinks from './components/RelatedLinks.vue'
import AiAssistant from './components/AiAssistant.vue'
import { installTimeAgo } from './timeAgo'
import { installScrollReveal } from './scrollReveal'
import { installLightbox } from './lightbox'
import { installReadingEnhancements } from './reading'
import { installParticles } from './particles'
import { installMicroInteractions } from './microInteractions'
import { installMascot } from './mascot'
import { installBoards } from './boards'

// 让站内链接走「整页加载」而不是 VitePress 的 SPA 前端路由。
// 原因：当前静态托管（CloudStudio Gateway）对每个深层链接都能稳定返回正确页面，
// 但 SPA 前端点击跳转偶发命中 VitePress 自带的 404 组件。
// 改为整页加载后，每次点击都等于直接打开那个本来就正常的页面，永不再 404。
function installFullNavigation() {
  const onDocClick = (e) => {
    if (e.defaultPrevented) return
    if (e.button !== 0) return // 只处理鼠标左键 / 回车
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return // 保留「新标签打开」
    const a = e.target.closest && e.target.closest('a')
    if (!a) return
    const href = a.getAttribute('href')
    if (!href) return
    if (a.target && a.target !== '_self') return
    if (href.startsWith('#') || href.startsWith('mailto:') || href.startsWith('tel:')) return
    if (/^[a-z][a-z0-9+.-]*:/i.test(href)) return // 外链（http/https/ftp...）
    let url
    try {
      url = new URL(href, location.href)
    } catch (_) {
      return
    }
    if (url.origin !== location.origin) return
    // 同页锚点：交给默认滚动行为，不整页刷新
    if (url.pathname === location.pathname && url.hash) return
    e.preventDefault()
    e.stopPropagation()
    window.location.assign(url.pathname + url.search + url.hash)
  }
  document.addEventListener('click', onDocClick, true)
}

const ThemeLayout = () => {
  return h(DefaultTheme.Layout, null, {
    'layout-bottom': () => [h(SiteFooter), h(AiAssistant)],
    // 每个文档页底部：打卡按钮（仅学习路径页显示）+ 跨板块相关推荐
    'doc-after': () => [h(ProgressCheck), h(RelatedLinks)]
  })
}

export default {
  extends: DefaultTheme,
  Layout: ThemeLayout,
  enhanceApp({ app }) {
    app.component('HomeBanner', HomeBanner)
    app.component('VideoEmbed', VideoEmbed)
    app.component('BiliEmbed', BiliEmbed)
    app.component('Step', Step)
    app.component('Steps', Steps)
    app.component('Callout', Callout)
    app.component('SiteSearch', SiteSearch)
    app.component('MiniTools', MiniTools)
    app.component('NewsLibrary', NewsLibrary)
    app.component('ProgressCheck', ProgressCheck)
    app.component('HomeProgress', HomeProgress)
    app.component('RelatedLinks', RelatedLinks)
    app.component('AiAssistant', AiAssistant)
  },
  setup() {
    // 让「X 分钟前更新」在浏览器里实时计算
    installTimeAgo()
    // 站内链接整页加载，避免 SPA 点击跳转偶发 404
    // 注意：setup() 在 VitePress 的 SSR（服务端渲染）阶段也会执行，
    // 此时没有 document，必须仅在浏览器端挂载点击监听。
    if (typeof document !== 'undefined') {
      // 每个模块单独兜底：任何一环出错都不影响其它功能，整站不会白屏
      const safe = (fn) => { try { fn() } catch (e) { /* 忽略单点故障 */ } }
      safe(installFullNavigation)
      safe(installScrollReveal)
      safe(installLightbox)
      safe(installReadingEnhancements)
      safe(installParticles)
      safe(installMicroInteractions)
      safe(installMascot)
      safe(installBoards)
    }
  }
}

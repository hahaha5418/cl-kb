import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const dir = path.dirname(fileURLToPath(import.meta.url))
const docs = path.resolve(dir, '..')

/* 读取一个 .md 文件的标题（优先 frontmatter 的 title，其次一级标题） */
function titleOf(file) {
  try {
    const raw = fs.readFileSync(file, 'utf8')
    const m = raw.match(/^---\r?\n([\s\S]*?)\r?\n---/)
    if (m) {
      const line = m[1].split(/\r?\n/).find((l) => l.startsWith('title:'))
      if (line) return line.slice(6).trim().replace(/^"|"$/g, '')
    }
    const h = raw.match(/^#\s+(.+)$/m)
    if (h) return h[1].trim()
  } catch (e) {}
  return path.basename(file, '.md')
}

/* 平铺目录 → 侧边栏分组 */
function flatGroup(folder, text) {
  const base = path.join(docs, folder)
  if (!fs.existsSync(base)) return { text, link: '/' + folder + '/', items: [] }
  const files = fs.readdirSync(base)
    .filter((f) => f.endsWith('.md') && f !== 'index.md')
  return {
    text,
    link: '/' + folder + '/',
    collapsed: true,
    items: files.map((f) => ({
      text: titleOf(path.join(base, f)),
      link: '/' + folder + '/' + f.replace(/\.md$/, '')
    }))
  }
}

/* 学习路径：stage-1 / stage-2 ... 两级分组 */
function pathGroup() {
  const base = path.join(docs, 'path')
  if (!fs.existsSync(base)) return { text: '学习路径', link: '/path/', items: [] }
  const subs = fs.readdirSync(base).filter((f) => fs.statSync(path.join(base, f)).isDirectory())
  return {
    text: '学习路径',
    link: '/path/',
    collapsed: true,
    items: subs.map((sd) => {
      const sub = path.join(base, sd)
      const files = fs.readdirSync(sub).filter((f) => f.endsWith('.md') && f !== 'index.md')
      return {
        text: titleOf(path.join(sub, 'index.md')),
        link: '/path/' + sd + '/',
        collapsed: true,
        items: files.map((f) => ({
          text: titleOf(path.join(sub, f)),
          link: '/path/' + sd + '/' + f.replace(/\.md$/, '')
        }))
      }
    })
  }
}

export default {
  // ⚠️ 如果用 GitHub Pages 部署，这里必须改成 "/你的仓库名/"
  //    如果用 Netlify / Vercel / Cloudflare Pages，改成 '/'
  base: process.env.VP_BASE || '/ai-kb/',

  // 预览/部署时绑定 0.0.0.0 并放行反向代理域名（否则 Vite 会拒绝请求）
  server: { host: true, allowedHosts: true },
  preview: { host: true, allowedHosts: true },

  lang: 'zh-CN',
  title: 'CL',
  description: 'CL 的个人 AI 知识库 · 每天学一点',
  ignoreDeadLinks: true,

  // —— SEO / 可发现性 / 可安装到手机主屏 ——
  head: [
    ['link', { rel: 'manifest', href: '/manifest.webmanifest' }],
    ['link', { rel: 'apple-touch-icon', href: '/icon.svg' }],
    ['meta', { name: 'theme-color', content: '#4f46e5' }],
    ['meta', { name: 'application-name', content: 'CL 知识库' }],
    ['meta', { property: 'og:site_name', content: 'CL · 个人 AI 知识库' }],
    ['meta', { property: 'og:title', content: 'CL · 个人 AI 知识库' }],
    ['meta', { property: 'og:description', content: '零基础每天学一点 AI：术语、路径、工具、热点、视频教程与小工具。' }],
    ['meta', { property: 'og:type', content: 'website' }],
    ['meta', { property: 'og:image', content: '/covers/home-banner.png' }],
    ['meta', { name: 'twitter:card', content: 'summary_large_image' }]
  ],

  themeConfig: {
    nav: [
      { text: '首页', link: '/' },
      { text: '时光引擎', link: '/time-engine.html' },
      {
        text: '🎮 玩法',
        items: [
          { text: '🎁 AI 盲盒挑战', link: '/blindbox.html' },
          { text: '🌳 技能树', link: '/skilltree.html' },
          { text: '🎬 视觉影音室', link: '/media.html' }
        ]
      },
      { text: '术语词典', link: '/glossary/' },
      { text: '学习路径', link: '/path/' },
      { text: '工具库', link: '/tools/' },
      { text: '每日热点', link: '/news/' },
      { text: 'AI 实操', link: '/dev/' },
      { text: '场景应用', link: '/scenes/' },
      { text: '视频教程', link: '/video/' },
      { text: '🔍 搜索', link: '/search.html' },
      { text: '🛠 小工具', link: '/utils/' },
      { text: '我的笔记', link: '/notes/' },
      { text: '使用说明', link: '/guide.html' }
    ],

    sidebar: {
      '/glossary/': [flatGroup('glossary', '术语词典')],
      '/path/': [pathGroup()],
      '/tools/': [flatGroup('tools', '工具库')],
      '/news/': [flatGroup('news', '每日热点')],
      '/dev/': [flatGroup('dev', 'AI 实操 / 开发进阶')],
      '/scenes/': [flatGroup('scenes', '场景应用')],
      '/video/': [flatGroup('video', '视频教程')],
      '/notes/': [flatGroup('notes', '我的笔记')],
      '/time-engine.html': [
        { text: '开始', items: [
          { text: '首页', link: '/' },
          { text: '时光引擎', link: '/time-engine.html' },
          { text: '🎁 AI 盲盒挑战', link: '/blindbox.html' },
          { text: '🌳 技能树', link: '/skilltree.html' },
          { text: '🎬 视觉影音室', link: '/media.html' }
        ]},
        pathGroup(),
        flatGroup('dev', 'AI 实操 / 开发进阶'),
        flatGroup('scenes', '场景应用'),
        flatGroup('notes', '我的笔记')
      ],
      '/': [
        { text: '开始', items: [
          { text: '首页', link: '/' },
          { text: '时光引擎', link: '/time-engine.html' },
          { text: '🎁 AI 盲盒挑战', link: '/blindbox.html' },
          { text: '🌳 技能树', link: '/skilltree.html' },
          { text: '🎬 视觉影音室', link: '/media.html' },
          { text: '使用说明', link: '/guide.html' }
        ]},
        flatGroup('glossary', '术语词典'),
        pathGroup(),
        flatGroup('tools', '工具库'),
        flatGroup('news', '每日热点'),
        flatGroup('dev', 'AI 实操 / 开发进阶'),
        flatGroup('scenes', '场景应用'),
        flatGroup('video', '视频教程'),
        { text: '🔍 全能搜索', link: '/search.html' },
        { text: '🛠 小工具', link: '/utils/' },
        flatGroup('notes', '我的笔记')
      ]
    },

    search: {
      provider: 'local',
      options: { miniSearch: { searchOptions: { fuzzy: 0.2, prefix: true } } }
    },

    outlineTitle: '本页目录',
    docFooter: { prev: '上一页', next: '下一页' },
    sidebarMenuLabel: '菜单',
    returnToTopLabel: '回到顶部',
    darkModeSwitchLabel: '主题',
    lightModeSwitchTitle: '切换到浅色',
    darkModeSwitchTitle: '切换到深色',
    externalLinkIcon: true,

    // 说明：这里原本有一个「在 GitHub 上编辑这一页」按钮，
    // 但它是跳到外部网站的外链，多数情况下打不开（404）。
    // 按「站内就能读完、不跳外网」的原则，已停用。
  }
}

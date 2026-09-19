<script setup>
/* 全站页脚：品牌 + 分栏链接 + 版权（模仿大厂站结构清晰的 footer） */
const cols = [
  {
    title: '学习',
    links: [
      { text: '今日任务', href: '/today.html' },
      { text: '学习路径', href: '/path/' },
      { text: '术语词典', href: '/glossary/' },
      { text: '我的笔记', href: '/notes/' }
    ]
  },
  {
    title: '实战',
    links: [
      { text: '工具库', href: '/tools/' },
      { text: 'AI 实操', href: '/dev/' },
      { text: '场景应用', href: '/scenes/' },
      { text: '每日热点', href: '/news/' }
    ]
  },
  {
    title: '关于',
    links: [
      { text: '使用说明', href: '/guide.html' },
      { text: '回到首页', href: '/' }
    ]
  }
]
const year = new Date().getFullYear()
</script>

<template>
  <footer class="cl-footer">
    <div class="cl-footer-inner">
      <div class="cl-footer-brand">
        <div class="cl-footer-logo">CL</div>
        <div class="cl-footer-tag">个人 AI 知识库 · 每天学一点，从看懂到上手</div>
        <div class="cl-footer-note">🌐 全中文 · 🔄 每日早 7 点自动更新 · 🚫 不跳外网，站内读完</div>
      </div>

      <nav class="cl-footer-cols">
        <div v-for="c in cols" :key="c.title" class="cl-footer-col">
          <h4 class="cl-footer-col-title">{{ c.title }}</h4>
          <a v-for="l in c.links" :key="l.href" class="cl-footer-link" :href="l.href">{{ l.text }}</a>
        </div>
      </nav>
    </div>

    <div class="cl-footer-bottom">
      <span>© {{ year }} CL · 内容由 AI 辅助整理，每日自动更新</span>
      <span class="cl-footer-sep">·</span>
      <span>仅供学习交流使用</span>
    </div>
  </footer>
</template>

<style scoped>
.cl-footer {
  margin-top: 48px;
  border-top: 1px solid var(--vp-c-border);
  background: linear-gradient(180deg, rgba(12, 12, 22, 0.4), rgba(8, 8, 15, 0.9));
}
.cl-footer-inner {
  max-width: 1152px;
  margin: 0 auto;
  padding: 40px 24px 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 36px;
  justify-content: space-between;
}
.cl-footer-brand { max-width: 320px; }
.cl-footer-logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 46px;
  height: 46px;
  border-radius: 13px;
  font-weight: 800;
  font-size: 1.2rem;
  color: #fff;
  background: linear-gradient(120deg, #8b5cf6, #6366f1 55%, #22d3ee);
  box-shadow: 0 8px 24px rgba(99, 102, 241, 0.4);
  margin-bottom: 12px;
}
.cl-footer-tag { color: var(--vp-c-text-1); font-weight: 700; font-size: 1rem; line-height: 1.5; }
.cl-footer-note { margin-top: 8px; color: var(--vp-c-text-3); font-size: .82rem; line-height: 1.7; }

.cl-footer-cols { display: flex; flex-wrap: wrap; gap: 40px; }
.cl-footer-col { display: flex; flex-direction: column; gap: 10px; min-width: 96px; }
.cl-footer-col-title {
  margin: 0 0 4px;
  font-size: .82rem;
  letter-spacing: .08em;
  color: var(--cl-cyan);
  text-transform: uppercase;
}
.cl-footer-link {
  color: var(--vp-c-text-2);
  text-decoration: none;
  font-size: .92rem;
  transition: color .2s;
}
.cl-footer-link:hover { color: #fff; }

.cl-footer-bottom {
  max-width: 1152px;
  margin: 0 auto;
  padding: 18px 24px 28px;
  border-top: 1px solid var(--vp-c-divider);
  margin-top: 28px;
  color: var(--vp-c-text-3);
  font-size: .8rem;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.cl-footer-sep { opacity: .5; }

@media (max-width: 640px) {
  .cl-footer-inner { padding: 32px 18px 4px; gap: 28px; }
  .cl-footer-cols { gap: 28px; }
}
</style>

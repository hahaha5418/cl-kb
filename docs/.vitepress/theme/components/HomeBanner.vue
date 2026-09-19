<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { withBase } from 'vitepress'

/* 首页主大图：用 withBase 保证在任何 base 路径下都能正确加载 */
const bannerImg = withBase('/covers/home-banner.png')
const bannerStyle = {
  backgroundImage:
    'linear-gradient(135deg, rgba(8,8,15,.80), rgba(8,8,15,.42) 55%, rgba(8,8,15,.78)), url(' + bannerImg + ')'
}

const slides = [
  { tag: '每日自动更新', title: '每天学一点 AI', sub: 'CL 的个人 AI 知识库 · 前沿热点 / 核心术语 / 学习路径 / 工具库，每天早 7 点自动刷新' },
  { tag: '零基础友好', title: '从看懂到上手', sub: '核心术语配中文讲解 · 26 步学习路径 · 跟着做就能懂' },
  { tag: '动手实操', title: '玩转 AI 工具', sub: 'API 调用 · AI Agent 搭建 · n8n/Dify 工作流 · PPT/视频/绘图场景实战' }
]

const active = ref(0)
let timer = null
onMounted(() => {
  timer = setInterval(() => { active.value = (active.value + 1) % slides.length }, 4500)
})
onUnmounted(() => clearInterval(timer))

/* 点击搜索条 → 打开 VitePress 本地搜索弹窗（大厂站标配的"命令面板"式搜索） */
function openSearch() {
  const btn = document.querySelector('.VPNavBarSearch .search-button')
    || document.querySelector('.VPNavBarSearch button')
    || document.querySelector('.VPNavBarSearch')
  if (btn) btn.click()
}

const trust = [
  { icon: '🌐', text: '全中文讲解' },
  { icon: '🔄', text: '每日早 7 点自动更新' },
  { icon: '📱', text: '手机 / 电脑都能用' },
  { icon: '🚫', text: '不跳外网，站内读完' }
]
</script>

<template>
  <div class="cl-banner" :style="bannerStyle">
    <div class="cl-banner-track">
      <div
        v-for="(s, i) in slides"
        :key="i"
        class="cl-slide"
        :class="{ active: i === active }"
      >
        <span class="cl-slide-tag">{{ s.tag }}</span>
        <h1 class="cl-slide-title">{{ s.title }}</h1>
        <p class="cl-slide-sub">{{ s.sub }}</p>

        <!-- 可见搜索条：点击打开站内搜索（模仿大厂站的搜索入口） -->
        <button class="cl-search" type="button" @click="openSearch" aria-label="搜索站内内容">
          <svg class="cl-search-ico" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
            <path fill="currentColor" d="M15.5 14h-.79l-.28-.27a6.5 6.5 0 1 0-.7.7l.27.28v.79l5 5 1.5-1.5-5-5Zm-6 0A4.5 4.5 0 1 1 14 9.5 4.5 4.5 0 0 1 9.5 14Z"/>
          </svg>
          <span class="cl-search-ph">搜索术语、工具、教程、热点…</span>
          <kbd class="cl-search-kbd">/</kbd>
        </button>

        <!-- 两个明确行动按钮 -->
        <div class="cl-cta">
          <a class="cl-btn cl-btn-primary" href="/path/">开始学习 →</a>
          <a class="cl-btn cl-btn-ghost" href="/news/">浏览今日热点</a>
        </div>
      </div>
    </div>

    <div class="cl-dots">
      <button
        v-for="(s, i) in slides"
        :key="i"
        :class="{ on: i === active }"
        :aria-label="'切换到第' + (i + 1) + '张'"
        @click="active = i"
      ></button>
    </div>

    <!-- 信任徽章行 -->
    <div class="cl-trust">
      <span v-for="(t, i) in trust" :key="i" class="cl-trust-item">
        <span class="cl-trust-ico">{{ t.icon }}</span>{{ t.text }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.cl-banner {
  position: relative;
  border-radius: 22px;
  overflow: hidden;
  margin: 14px 0 10px;
  min-height: 250px;
  border: 1px solid var(--vp-c-border);
  box-shadow: 0 18px 50px rgba(76, 29, 149, 0.35);
  background: linear-gradient(135deg, rgba(124, 58, 237, 0.40), rgba(34, 211, 238, 0.18) 55%, rgba(236, 72, 153, 0.24));
  background-size: cover;
  background-position: center;
  padding-bottom: 52px; /* 给信任徽章行留位 */
}
.cl-banner::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(42vw 42vw at 82% 18%, rgba(34, 211, 238, 0.28), transparent 60%),
    radial-gradient(42vw 42vw at 18% 92%, rgba(236, 72, 153, 0.24), transparent 60%);
  animation: clBannerFloat 14s ease-in-out infinite alternate;
}
@keyframes clBannerFloat {
  0%   { transform: translate(0, 0) scale(1); }
  100% { transform: translate(-3%, 2%) scale(1.06); }
}
.cl-slide {
  position: absolute;
  inset: 0;
  padding: 40px 44px 24px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  opacity: 0;
  transform: translateY(16px);
  transition: opacity .6s ease, transform .6s ease;
  pointer-events: none;
}
.cl-slide.active {
  opacity: 1;
  transform: none;
  position: relative;
  pointer-events: auto;
}
.cl-slide-tag {
  align-self: flex-start;
  font-size: .72rem;
  padding: 3px 12px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.32);
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.35);
  backdrop-filter: blur(4px);
}
.cl-slide-title {
  font-size: clamp(1.9rem, 4.2vw, 2.9rem);
  margin: 14px 0 10px;
  font-weight: 800;
  line-height: 1.15;
  background: linear-gradient(120deg, #ffffff, #c4b5fd 58%, #67e8f9);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
.cl-slide-sub {
  color: rgba(255, 255, 255, 0.88);
  font-size: 1rem;
  max-width: 580px;
  line-height: 1.6;
}

/* —— 可见搜索条 —— */
.cl-search {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 18px;
  width: 100%;
  max-width: 520px;
  padding: 12px 16px;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.28);
  background: rgba(8, 8, 18, 0.55);
  color: #fff;
  cursor: text;
  backdrop-filter: blur(8px);
  transition: border-color .2s, box-shadow .2s, background .2s;
  text-align: left;
}
.cl-search:hover,
.cl-search:focus-visible {
  border-color: var(--cl-cyan);
  box-shadow: 0 0 0 3px rgba(34, 211, 238, 0.22);
  background: rgba(8, 8, 18, 0.7);
  outline: none;
}
.cl-search-ico { color: var(--cl-cyan); flex: none; }
.cl-search-ph { flex: 1; color: rgba(255, 255, 255, 0.6); font-size: .95rem; }
.cl-search-kbd {
  flex: none;
  font-size: .8rem;
  padding: 2px 9px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: rgba(255, 255, 255, 0.85);
  background: rgba(255, 255, 255, 0.06);
}

/* —— 行动按钮 —— */
.cl-cta { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 16px; }
.cl-btn {
  display: inline-flex;
  align-items: center;
  font-weight: 700;
  font-size: .98rem;
  padding: 11px 22px;
  border-radius: 12px;
  text-decoration: none;
  transition: transform .2s, box-shadow .2s, background .2s, border-color .2s;
}
.cl-btn:hover { transform: translateY(-2px); }
.cl-btn-primary {
  color: #fff;
  background: linear-gradient(120deg, #8b5cf6, #6366f1 55%, #22d3ee);
  box-shadow: 0 10px 30px rgba(99, 102, 241, 0.45);
}
.cl-btn-primary:hover { box-shadow: 0 14px 38px rgba(99, 102, 241, 0.6); }
.cl-btn-ghost {
  color: #fff;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.3);
}
.cl-btn-ghost:hover { background: rgba(255, 255, 255, 0.16); border-color: #fff; }

.cl-dots {
  position: absolute;
  bottom: 18px;
  left: 44px;
  display: flex;
  gap: 8px;
  z-index: 2;
}
.cl-dots button {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  border: none;
  background: rgba(255, 255, 255, 0.4);
  cursor: pointer;
  transition: .25s;
  padding: 0;
}
.cl-dots button.on {
  background: #fff;
  width: 24px;
  border-radius: 6px;
}

/* —— 信任徽章行 —— */
.cl-trust {
  position: absolute;
  left: 0; right: 0; bottom: 0;
  z-index: 2;
  display: flex;
  flex-wrap: wrap;
  gap: 10px 22px;
  padding: 14px 44px;
  border-top: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(8, 8, 18, 0.4);
  backdrop-filter: blur(6px);
}
.cl-trust-item {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: .82rem;
  color: rgba(255, 255, 255, 0.82);
}
.cl-trust-ico { font-size: 1rem; }

@media (max-width: 640px) {
  .cl-slide { padding: 26px 20px 18px; }
  .cl-slide-sub { font-size: .9rem; }
  .cl-dots { left: 20px; bottom: 14px; }
  .cl-trust { padding: 12px 20px; gap: 8px 14px; }
  .cl-trust-item { font-size: .76rem; }
  .cl-btn { padding: 10px 18px; font-size: .92rem; }
}
</style>

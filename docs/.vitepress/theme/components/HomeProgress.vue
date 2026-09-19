<!-- 首页学习进度条：读 path-manifest.json 得到路径总步数，结合 localStorage 计算完成百分比 -->
<template>
  <div class="cl-prog">
    <div class="cl-prog-top">
      <span>🎯 我的学习进度</span>
      <b>{{ done }} / {{ total }} 步 · {{ pct }}%</b>
    </div>
    <div class="cl-prog-bar">
      <div class="cl-prog-fill" :style="{ width: pct + '%' }"></div>
    </div>
    <p class="cl-prog-tip">
      去 <a href="/path/">学习路径</a> 每个任务点「标记完成」即可累计；进度只存在你本机浏览器。
    </p>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { progressState, loadProgress } from '../progress'

const total = ref(0)
const done = computed(() =>
  Object.keys(progressState.steps).filter((k) => progressState.steps[k]).length
)
const pct = computed(() => (total.value ? Math.round((done.value / total.value) * 100) : 0))

onMounted(async () => {
  loadProgress()
  try {
    const base = import.meta.env.BASE_URL || '/'
    const res = await fetch(base + 'path-manifest.json')
    const data = await res.json()
    total.value = (data.steps || []).length
  } catch (e) {
    /* manifest 缺失时用 0，不影响其它功能 */
  }
})
</script>

<style>
.cl-prog {
  margin: 18px 0 8px;
  padding: 16px 18px;
  border: 1px solid var(--vp-c-border);
  border-radius: 14px;
  background: var(--vp-c-bg-soft);
}
.cl-prog-top {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 10px;
}
.cl-prog-top b { color: var(--vp-c-brand-1); font-size: 14px; }
.cl-prog-bar {
  height: 10px;
  border-radius: 999px;
  background: rgba(139, 92, 246, .15);
  overflow: hidden;
}
.cl-prog-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #8b5cf6, #6366f1, #22d3ee);
  transition: width .4s ease;
}
.cl-prog-tip { margin: 10px 0 0; font-size: 12px; color: var(--vp-c-text-2); }
.cl-prog-tip a { color: var(--vp-c-brand-1); }
</style>

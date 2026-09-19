<template>
  <div v-if="ready && node && node.related.length" class="rl-wrap">
    <h2 class="rl-h">
      🔗 相关推荐
      <span class="rl-sub">来自其它板块的同类内容，点开接着学</span>
    </h2>
    <div class="rl-list">
      <a
        v-for="(r, i) in node.related"
        :key="r.url + '#' + i"
        class="rl-item"
        :href="r.url"
      >
        <span class="rl-badge" :class="'rl-' + r.type">{{ r.label }}</span>
        <span class="rl-title">{{ r.title }}</span>
        <span class="rl-arrow">→</span>
      </a>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vitepress'

const route = useRoute()
const graph = ref(null)
const ready = ref(false)
const node = ref(null)

// VitePress 路由路径形如 /dev/01-api-calling.html 或 /dev/（索引页）；
// 与链接图谱里的 url 对齐（索引页不在图谱中，自然不会显示相关推荐）。
function normKey(p) {
  let k = p || '/'
  if (k.endsWith('/')) k += 'index.html'
  if (!k.endsWith('.html') && !k.endsWith('.json')) k += '.html'
  return k
}

function resolve() {
  if (!graph.value) return
  node.value = graph.value.byUrl[normKey(route.path)] || null
}

onMounted(async () => {
  try {
    const base = import.meta.env.BASE_URL || '/'
    const res = await fetch(base + 'links-graph.json')
    graph.value = await res.json()
  } catch (_) {
    /* 图谱缺失时静默降级，不影响页面其余内容 */
  }
  ready.value = true
  resolve()
})

// 站内跳转（SPA）时重新匹配当前页
watch(() => route.path, () => resolve())
</script>

<style>
.rl-wrap {
  margin: 2.4rem 0 1rem;
  padding-top: 1.4rem;
  border-top: 1px dashed var(--vp-c-border);
}
.rl-h {
  font-size: 1.05rem;
  font-weight: 700;
  margin: 0 0 1rem;
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
}
.rl-sub {
  font-size: 0.78rem;
  font-weight: 400;
  color: var(--vp-c-text-2);
}
.rl-list {
  display: grid;
  gap: 8px;
}
.rl-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border: 1px solid var(--vp-c-border);
  border-radius: 10px;
  background: var(--vp-c-bg);
  text-decoration: none;
  color: var(--vp-c-text-1);
  transition: border-color 0.15s, transform 0.15s, box-shadow 0.15s;
}
.rl-item:hover {
  border-color: var(--vp-c-brand-1);
  transform: translateX(3px);
  box-shadow: 0 4px 14px rgba(124, 58, 237, 0.18);
}
.rl-badge {
  flex: none;
  font-size: 0.72rem;
  padding: 2px 9px;
  border-radius: 999px;
  background: rgba(124, 58, 237, 0.14);
  color: var(--vp-c-brand-1);
  border: 1px solid rgba(124, 58, 237, 0.3);
}
.rl-glossary { background: rgba(34, 211, 238, 0.14); color: var(--cl-cyan); border-color: rgba(34, 211, 238, 0.3); }
.rl-news { background: rgba(236, 72, 153, 0.14); color: #ec4899; border-color: rgba(236, 72, 153, 0.3); }
.rl-dev { background: rgba(124, 58, 237, 0.14); color: #a78bfa; border-color: rgba(124, 58, 237, 0.3); }
.rl-scenes { background: rgba(99, 102, 241, 0.14); color: #818cf8; border-color: rgba(99, 102, 241, 0.3); }
.rl-path { background: rgba(16, 185, 129, 0.14); color: #34d399; border-color: rgba(16, 185, 129, 0.3); }
.rl-tools { background: rgba(245, 158, 11, 0.14); color: #fbbf24; border-color: rgba(245, 158, 11, 0.3); }
.rl-notes { background: rgba(148, 163, 184, 0.16); color: #cbd5e1; border-color: rgba(148, 163, 184, 0.3); }
.rl-title {
  flex: 1;
  min-width: 0;
  font-size: 0.92rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.rl-arrow { flex: none; color: var(--vp-c-brand-1); }

@media (max-width: 640px) {
  .rl-item { padding: 9px 11px; }
  .rl-title { font-size: 0.85rem; white-space: normal; }
}
</style>

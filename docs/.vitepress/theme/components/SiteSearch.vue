<template>
  <div class="cl-search-page">
    <div class="cl-search-box">
      <span class="cl-search-ico">🔍</span>
      <input
        ref="input"
        v-model="q"
        class="cl-search-input"
        type="text"
        placeholder="搜文章、工具、术语、标签…（输入即出结果）"
        @input="run"
        @keydown.down.prevent="move(1)"
        @keydown.up.prevent="move(-1)"
        @keydown.enter.prevent="go(results[active] || results[0])"
        @keydown.esc="clear"
      />
      <button v-if="q" class="cl-search-clear" title="清空" @click="clear">✕</button>
    </div>

    <div v-if="loading" class="cl-search-hint">正在加载搜索库…</div>
    <div v-else-if="q && !results.length" class="cl-search-hint">没有匹配「{{ q }}」的内容</div>
    <div v-else-if="!q" class="cl-search-hint">
      试试搜：<code>ChatGPT</code> · <code>提示词</code> · <code>Agent</code> · <code>PPT</code> · <code>视频生成</code> · <code>本地部署</code>
    </div>

    <ul v-if="results.length" class="cl-search-results">
      <li
        v-for="(r, i) in results"
        :key="r.url"
        :class="['cl-search-item', { active: i === active }]"
        @mouseenter="active = i"
        @click="go(r)"
      >
        <span class="cl-search-cat">{{ r.category }}</span>
        <span class="cl-search-title">{{ r.title }}</span>
        <span v-if="r.desc" class="cl-search-desc">{{ r.desc }}</span>
        <span v-if="r.tags && r.tags.length" class="cl-search-tags">
          <span v-for="t in r.tags.slice(0, 4)" :key="t" class="cl-search-tag">{{ t }}</span>
        </span>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const q = ref('')
const results = ref([])
const active = ref(0)
const loading = ref(true)
const input = ref(null)
let index = []

const norm = (s) => (s || '').toLowerCase().trim()

function scoreItem(item, query) {
  const qn = norm(query)
  if (!qn) return 0
  const tokens = qn.split(/\s+/).filter(Boolean)
  let score = 0
  const title = norm(item.title)
  const cat = norm(item.category)
  const tags = (item.tags || []).map(norm)
  const desc = norm(item.desc)
  const text = norm(item.text)
  for (const tk of tokens) {
    let s = 0
    if (title === tk) s += 60
    else if (title.startsWith(tk)) s += 40
    else if (title.includes(tk)) s += 25
    if (cat.includes(tk)) s += 12
    if (tags.some((t) => t === tk)) s += 20
    else if (tags.some((t) => t.includes(tk))) s += 10
    if (desc.includes(tk)) s += 6
    if (text.includes(tk)) s += 3
    if (s === 0) return 0 // 每个关键词都要命中（AND 逻辑）
    score += s
  }
  return score
}

function run() {
  active.value = 0
  const qn = norm(q.value)
  if (!qn || !index.length) {
    results.value = []
    return
  }
  results.value = index
    .map((it) => ({ it, s: scoreItem(it, q.value) }))
    .filter((x) => x.s > 0)
    .sort((a, b) => b.s - a.s)
    .slice(0, 14)
    .map((x) => x.it)
}

function move(d) {
  if (!results.value.length) return
  const n = results.value.length
  active.value = (active.value + d + n) % n
}
function go(r) {
  if (!r) return
  window.location.assign(r.url)
}
function clear() {
  q.value = ''
  results.value = []
  if (input.value) input.value.focus()
}

onMounted(async () => {
  try {
    const base = import.meta.env.BASE_URL || '/'
    const res = await fetch(base + 'search-index.json')
    index = await res.json()
  } catch (e) {
    console.warn('搜索索引加载失败', e)
  } finally {
    loading.value = false
    if (input.value) input.value.focus()
  }
})
</script>

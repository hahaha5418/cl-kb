<template>
  <div class="nl-wrap">
    <div v-if="loading" class="nl-hint">正在加载热点详情库…</div>
    <div v-else-if="loadError" class="nl-hint">热点库加载失败，刷新页面重试即可。</div>

    <template v-else>
      <div class="nl-bar">
        <input
          v-model="q"
          class="nl-input"
          type="text"
          placeholder="🔍 搜索标题、摘要、公司或模型…"
        />
        <select v-model="src" class="nl-sel">
          <option value="">全部来源</option>
          <option v-for="s in sources" :key="s" :value="s">{{ s }}</option>
        </select>
        <select v-model="day" class="nl-sel">
          <option value="">全部日期</option>
          <option v-for="d in dates" :key="d" :value="d">{{ d }}</option>
        </select>
      </div>

      <div class="nl-tags">
        <button :class="['nl-chip', { on: !tag }]" @click="tag = ''">全部 {{ total }}</button>
        <button
          v-for="t in tags"
          :key="t.name"
          :class="['nl-chip', { on: tag === t.name }]"
          @click="tag = tag === t.name ? '' : t.name"
        >{{ t.name }} {{ t.count }}</button>
      </div>

      <div class="nl-stat">
        <span>筛选出 <b>{{ filteredCount }}</b> 条 · 全站共 {{ total }} 条</span>
        <button v-if="open.size" class="nl-mini" @click="open = new Set()">全部收起</button>
      </div>

      <div v-if="!groups.length" class="nl-hint">没有符合条件的热点，换个关键词试试。</div>

      <section v-for="g in groups" :key="g.date" class="nl-group">
        <h2 class="nl-date">
          {{ g.date }} <span class="nl-week">{{ weekday(g.date) }}</span>
          <span class="nl-count">{{ g.items.length }} 条</span>
        </h2>

        <article
          v-for="it in g.items"
          :key="it.id"
          :class="['nl-card', { open: open.has(it.id) }]"
        >
          <div class="nl-head" @click="toggle(it.id)">
            <div class="nl-head-main">
              <h3 class="nl-title">{{ it.title }}</h3>
              <p class="nl-sum">{{ it.summary }}</p>
            </div>
            <span class="nl-toggle">{{ open.has(it.id) ? '收起' : '展开' }}</span>
          </div>

          <div class="nl-meta">
            <span class="nl-src">📰 {{ it.source || '未标注来源' }}</span>
            <span class="nl-time">🕒 {{ fmtTime(it.publishedAt) }}</span>
            <span v-for="t in it.tags" :key="t" class="nl-tag">{{ t }}</span>
            <span v-if="!it.detail" class="nl-tag pending">摘要生成中</span>
          </div>

          <div v-show="open.has(it.id)" class="nl-body">
            <img
              v-if="it.image && !broken[it.id]"
              class="nl-img"
              :src="it.image"
              alt="主题示意图"
              loading="lazy"
              @error="broken[it.id] = true"
            />

            <div class="nl-sec">
              <h4>📖 详细摘要</h4>
              <p v-if="it.detail" class="nl-detail">{{ it.detail }}</p>
              <p v-else class="nl-muted">这条的详细摘要还没生成，下次自动更新时会补上。</p>
            </div>

            <div v-if="it.points && it.points.length" class="nl-sec">
              <h4>🔑 关键要点</h4>
              <ol class="nl-points">
                <li v-for="(p, i) in it.points" :key="i">{{ p }}</li>
              </ol>
            </div>

            <div v-if="it.quotes && it.quotes.length" class="nl-sec">
              <h4>💬 原文摘录</h4>
              <blockquote v-for="(q2, i) in it.quotes" :key="i" class="nl-quote">
                <p class="nl-q-text">“{{ q2.text }}”</p>
                <p v-if="q2.note" class="nl-q-note">{{ q2.note }}</p>
              </blockquote>
            </div>

            <div v-if="entList(it).length" class="nl-sec">
              <h4>🏷️ 涉及对象</h4>
              <div class="nl-ents">
                <span v-for="e in entList(it)" :key="e.k + e.v" :class="['nl-ent', e.k]">
                  {{ e.label }}：{{ e.v }}
                </span>
              </div>
            </div>

            <div v-if="it.advice && (it.advice.learn || it.advice.do)" class="nl-advice">
              <h4>🎯 对我的学习建议</h4>
              <p v-if="it.advice.learn"><b>今天学什么：</b>{{ it.advice.learn }}</p>
              <p v-if="it.advice.do"><b>今天做什么：</b>{{ it.advice.do }}</p>
            </div>

            <div class="nl-foot">
              <a v-if="it.url" :href="it.url" target="_blank" rel="noopener">🔗 查看原文</a>
              <a v-if="it.link" :href="it.link" class="nl-detail-link">📄 站内详情页</a>
            </div>
          </div>
        </article>
      </section>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted } from 'vue'

const loading = ref(true)
const loadError = ref(false)
const days = ref([])
const total = ref(0)
const sources = ref([])
const tags = ref([])

const q = ref('')
const src = ref('')
const day = ref('')
const tag = ref('')
const open = ref(new Set())
const broken = reactive({})

function toggle(id) {
  const s = new Set(open.value)
  s.has(id) ? s.delete(id) : s.add(id)
  open.value = s
}

const weekday = (d) => {
  const w = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  const t = new Date(d + 'T00:00:00')
  return isNaN(t) ? '' : w[t.getDay()]
}

function fmtTime(ts) {
  if (!ts) return ''
  const s = String(ts).replace('T', ' ').slice(0, 16)
  return s
}

const all = computed(() => days.value.flatMap((d) => d.items.map((i) => ({ ...i, date: d.date }))))

const filtered = computed(() => {
  const kw = q.value.trim().toLowerCase()
  return all.value.filter((it) => {
    if (src.value && it.source !== src.value) return false
    if (day.value && it.date !== day.value) return false
    if (tag.value && !(it.tags || []).includes(tag.value)) return false
    if (!kw) return true
    const hay = [
      it.title, it.summary, it.detail,
      (it.points || []).join(' '),
      (it.tags || []).join(' '),
      Object.values(it.entities || {}).flat().join(' '),
    ].join(' ').toLowerCase()
    return hay.includes(kw)
  })
})

const dates = computed(() => days.value.map((d) => d.date))
const filteredCount = computed(() => filtered.value.length)

const groups = computed(() => {
  const m = new Map()
  filtered.value.forEach((it) => {
    if (!m.has(it.date)) m.set(it.date, [])
    m.get(it.date).push(it)
  })
  return [...m.entries()].map(([date, items]) => ({ date, items }))
})

function entList(it) {
  const e = it.entities || {}
  const out = []
  ;(e.companies || []).forEach((v) => out.push({ k: 'c', label: '公司', v }))
  ;(e.models || []).forEach((v) => out.push({ k: 'm', label: '模型', v }))
  ;(e.tools || []).forEach((v) => out.push({ k: 't', label: '工具', v }))
  return out
}

onMounted(async () => {
  try {
    const base = import.meta.env.BASE_URL || '/'
    const res = await fetch(base + 'news-library.json')
    const data = await res.json()
    days.value = data.days || []
    total.value = data.total || 0
    sources.value = data.sources || []
    tags.value = data.tags || []
  } catch (e) {
    loadError.value = true
  } finally {
    loading.value = false
  }
})
</script>

<style>
.nl-wrap { margin: 1rem 0 2rem; }
.nl-hint {
  padding: 1.5rem; text-align: center; color: var(--vp-c-text-2);
  background: var(--vp-c-bg-soft); border-radius: 12px; font-size: 14px;
}
.nl-bar { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
.nl-input, .nl-sel {
  border: 1px solid var(--vp-c-border); border-radius: 8px;
  background: var(--vp-c-bg); color: var(--vp-c-text-1);
  padding: 8px 12px; font-size: 14px; outline: none;
}
.nl-input { flex: 1 1 240px; min-width: 180px; }
.nl-sel { flex: 0 0 auto; }
.nl-input:focus, .nl-sel:focus { border-color: var(--vp-c-brand-1); }
.nl-tags { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }
.nl-chip {
  border: 1px solid var(--vp-c-border); background: var(--vp-c-bg);
  color: var(--vp-c-text-2); border-radius: 999px; padding: 4px 12px;
  font-size: 13px; cursor: pointer; transition: all .15s;
}
.nl-chip:hover { border-color: var(--vp-c-brand-1); color: var(--vp-c-text-1); }
.nl-chip.on {
  background: var(--vp-c-brand-1); border-color: var(--vp-c-brand-1); color: #fff;
}
.nl-stat {
  display: flex; justify-content: space-between; align-items: center;
  font-size: 13px; color: var(--vp-c-text-2); margin-bottom: 14px;
}
.nl-mini {
  border: 1px solid var(--vp-c-border); background: transparent;
  color: var(--vp-c-text-2); border-radius: 6px; padding: 3px 10px;
  font-size: 12px; cursor: pointer;
}
.nl-group { margin-bottom: 26px; }
.nl-date {
  font-size: 15px; font-weight: 600; margin: 0 0 12px;
  padding-bottom: 8px; border-bottom: 1px solid var(--vp-c-border);
  display: flex; align-items: baseline; gap: 8px;
}
.nl-week { font-size: 12px; font-weight: 400; color: var(--vp-c-text-2); }
.nl-count {
  margin-left: auto; font-size: 12px; font-weight: 400; color: var(--vp-c-text-2);
}
.nl-card {
  border: 1px solid var(--vp-c-border); border-radius: 12px;
  background: var(--vp-c-bg); padding: 14px 16px; margin-bottom: 10px;
  transition: border-color .15s, box-shadow .15s;
}
.nl-card:hover { border-color: var(--vp-c-brand-1); }
.nl-card.open { border-color: var(--vp-c-brand-1); box-shadow: 0 2px 12px rgba(0,0,0,.06); }
.nl-head { display: flex; gap: 12px; align-items: flex-start; cursor: pointer; }
.nl-head-main { flex: 1; min-width: 0; }
.nl-title { font-size: 16px; font-weight: 600; margin: 0 0 4px; line-height: 1.4; }
.nl-sum { margin: 0; font-size: 14px; color: var(--vp-c-text-2); line-height: 1.6; }
.nl-toggle { flex: none; font-size: 12px; color: var(--vp-c-brand-1); }
.nl-meta {
  display: flex; gap: 10px; flex-wrap: wrap; align-items: center;
  margin-top: 10px; font-size: 12px; color: var(--vp-c-text-2);
}
.nl-tag {
  background: var(--vp-c-bg-soft); border-radius: 999px; padding: 2px 9px;
}
.nl-tag.pending { color: var(--vp-c-warning-1); }
.nl-body { margin-top: 14px; padding-top: 14px; border-top: 1px dashed var(--vp-c-border); }
.nl-img {
  width: 100%; max-width: 260px; border-radius: 8px; margin-bottom: 14px; display: block;
}
.nl-sec { margin-bottom: 16px; }
.nl-sec h4 { font-size: 13px; font-weight: 600; margin: 0 0 6px; color: var(--vp-c-text-1); }
.nl-detail { margin: 0; font-size: 14px; line-height: 1.8; color: var(--vp-c-text-1); }
.nl-muted { margin: 0; font-size: 13px; color: var(--vp-c-text-3); }
.nl-points { margin: 0; padding-left: 20px; font-size: 14px; line-height: 1.8; }
.nl-quote {
  margin: 0 0 10px; padding: 8px 12px; border-left: 3px solid var(--vp-c-brand-1);
  background: var(--vp-c-bg-soft); border-radius: 0 8px 8px 0;
}
.nl-q-text { margin: 0 0 4px; font-size: 13px; font-style: italic; }
.nl-q-note { margin: 0; font-size: 12px; color: var(--vp-c-text-2); }
.nl-ents { display: flex; gap: 6px; flex-wrap: wrap; }
.nl-ent {
  font-size: 12px; padding: 3px 10px; border-radius: 999px;
  background: var(--vp-c-bg-soft); border: 1px solid var(--vp-c-border);
}
.nl-ent.m { border-color: var(--vp-c-brand-1); color: var(--vp-c-brand-1); }
.nl-ent.t { border-color: var(--vp-c-green-1); color: var(--vp-c-green-1); }
.nl-advice {
  background: var(--vp-c-bg-soft); border-radius: 10px; padding: 12px 14px; margin-bottom: 14px;
}
.nl-advice h4 { font-size: 13px; font-weight: 600; margin: 0 0 8px; }
.nl-advice p { margin: 0 0 6px; font-size: 13px; line-height: 1.7; }
.nl-advice p:last-child { margin-bottom: 0; }
.nl-foot { display: flex; gap: 16px; flex-wrap: wrap; font-size: 13px; }
.nl-foot a { color: var(--vp-c-brand-1); text-decoration: none; }
.nl-foot a:hover { text-decoration: underline; }
.nl-detail-link { color: var(--vp-c-text-2) !important; }

/* 手机端：筛选栏换行占满、图片铺满、字号收紧 */
@media (max-width: 640px) {
  .nl-bar { gap: 6px; }
  .nl-input { flex: 1 1 100%; min-width: 0; }
  .nl-sel { flex: 1 1 calc(50% - 3px); }
  .nl-title { font-size: 15px; }
  .nl-card { padding: 12px 12px; }
  .nl-img { max-width: 100%; }
  .nl-foot { gap: 10px; }
  .nl-stat { flex-wrap: wrap; gap: 6px; }
  .nl-sum { font-size: 13px; }
}
</style>

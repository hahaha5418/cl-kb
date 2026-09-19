/* ============================================================
   boards.js —— 第二步新板块的交互
   时光引擎（打卡 + 优先级）/ AI 盲盒 / 技能树
   全部纯前端：数据存在浏览器 localStorage，不联网、不请求后端、不会 404
   ============================================================ */

const K_TE_DONE = 'aikb.te.done'
const K_TE_LEVEL = 'aikb.te.level'
const K_BB = 'aikb.bb'
const K_ST = 'aikb.st.lit'

function lsGet(k, fb) {
  try {
    const v = localStorage.getItem(k)
    return v == null ? fb : JSON.parse(v)
  } catch (e) { return fb }
}

function lsSet(k, v) {
  try { localStorage.setItem(k, JSON.stringify(v)) } catch (e) {}
}

function todayKey() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate())
}

/* 用日期做种子，保证「今天」所有人抽到的是同一个（刷新不变） */
function hashMod(str, mod) {
  let h = 0
  for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) >>> 0
  return mod > 0 ? h % mod : 0
}

function pulse(el) {
  if (!el) return
  el.classList.remove('cl-pulse')
  // 强制重排，保证连续点击也能重新触发动画
  void el.offsetWidth
  el.classList.add('cl-pulse')
  setTimeout(() => el.classList.remove('cl-pulse'), 620)
}

/* ---------- 时光引擎：打卡 + 优先级 ---------- */
function installTimeEngine(root) {
  const box = root.querySelector('.cl-te')
  if (!box || box.getAttribute('data-boards') === '1') return
  box.setAttribute('data-boards', '1')
  const tasks = box.querySelectorAll('.cl-te-task')
  if (!tasks.length) return
  const done = new Set(lsGet(K_TE_DONE, []))
  const levels = lsGet(K_TE_LEVEL, {})
  const ORDER = ['must', 'urgent', 'normal']
  const LABEL = { must: '必做', urgent: '重要紧急', normal: '常规' }

  tasks.forEach((el) => {
    const key = el.getAttribute('data-key') || ''

    /* 打卡 */
    const chk = el.querySelector('.cl-te-check')
    if (chk) {
      if (done.has(key)) el.classList.add('is-checked')
      chk.addEventListener('click', (e) => {
        e.preventDefault()
        e.stopPropagation()
        if (done.has(key)) { done.delete(key); el.classList.remove('is-checked') }
        else { done.add(key); el.classList.add('is-checked'); pulse(el) }
        lsSet(K_TE_DONE, Array.from(done))
      })
    }

    /* 优先级切换 */
    const lvBtn = el.querySelector('.cl-te-level')
    if (lvBtn) {
      let cur = levels[key] || lvBtn.getAttribute('data-level') || 'normal'
      const apply = () => {
        lvBtn.setAttribute('data-level', cur)
        lvBtn.textContent = LABEL[cur] || cur
      }
      apply()
      lvBtn.addEventListener('click', (e) => {
        e.preventDefault()
        e.stopPropagation()
        cur = ORDER[(ORDER.indexOf(cur) + 1) % ORDER.length]
        levels[key] = cur
        lsSet(K_TE_LEVEL, levels)
        apply()
        pulse(el)
      })
    }
  })
}

/* ---------- AI 盲盒挑战 ---------- */
function installBlindBox(root) {
  const pool = document.getElementById('cl-bb-pool')
  const slot = document.getElementById('cl-bb-slot')
  if (!pool || !slot || pool.getAttribute('data-boards') === '1') return
  pool.setAttribute('data-boards', '1')
  const box = document.getElementById('cl-bb-box')
  const again = document.getElementById('cl-bb-again')
  const doneBtn = document.getElementById('cl-bb-done')
  const stat = document.getElementById('cl-bb-stat')

  const cards = Array.prototype.slice.call(pool.querySelectorAll('.cl-bb-card'))
  if (!cards.length) return

  const st = lsGet(K_BB, { date: '', idx: -1, done: [] })
  if (!Array.isArray(st.done)) st.done = []
  const tk = todayKey()

  let idx = st.idx
  if (st.date !== tk || idx < 0 || idx >= cards.length) {
    idx = hashMod(tk + '|bb', cards.length)
    st.date = tk
    st.idx = idx
    lsSet(K_BB, st)
  }

  function updateStat() {
    if (stat) stat.textContent = '已完成 ' + st.done.length + ' / ' + cards.length + ' 个挑战'
    if (doneBtn) doneBtn.textContent = st.done.indexOf(idx) >= 0 ? '↩️ 取消完成' : '✅ 标记已完成'
    const cur = slot.querySelector('.cl-bb-card')
    if (cur) cur.classList.toggle('is-finished', st.done.indexOf(idx) >= 0)
  }

  function render(i, animate) {
    idx = i
    st.idx = i
    slot.innerHTML = ''
    const card = cards[i].cloneNode(true)
    card.classList.add('is-out')
    if (animate) card.classList.add('cl-bb-pop')
    slot.appendChild(card)
    lsSet(K_BB, st)
    updateStat()
  }

  if (box) {
    box.addEventListener('click', () => render(idx, true))
  }
  if (again) {
    again.addEventListener('click', () => {
      let n = idx
      if (cards.length > 1) {
        n = Math.floor(Math.random() * cards.length)
        if (n === idx) n = (n + 1) % cards.length
      }
      render(n, true)
    })
  }
  if (doneBtn) {
    doneBtn.addEventListener('click', () => {
      const p = st.done.indexOf(idx)
      if (p >= 0) st.done.splice(p, 1)
      else st.done.push(idx)
      lsSet(K_BB, st)
      updateStat()
      pulse(slot.querySelector('.cl-bb-card'))
    })
  }

  updateStat()
  // 进来就自动开盒（每天固定一个），保留盒子动画
  setTimeout(() => render(idx, true), 420)
}

/* ---------- 技能树 ---------- */
function installSkillTree(root) {
  const wrap = root.querySelector('.cl-st')
  if (!wrap || wrap.getAttribute('data-boards') === '1') return
  wrap.setAttribute('data-boards', '1')
  const nodes = Array.prototype.slice.call(wrap.querySelectorAll('.cl-st-node'))
  if (!nodes.length) return

  const lit = new Set(lsGet(K_ST, []))
  const lvEl = document.getElementById('cl-st-lv')
  const lvNameEl = document.getElementById('cl-st-lvname')
  const countEl = document.getElementById('cl-st-count')
  const xpEl = document.getElementById('cl-st-xp')
  const barEl = document.getElementById('cl-st-bar')
  const resetBtn = document.getElementById('cl-st-reset')

  const totalXp = nodes.reduce((s, n) => s + (Number(n.getAttribute('data-xp')) || 10), 0)
  const TIERS = [
    [0.12, 'Lv.1', 'AI 新手'],
    [0.30, 'Lv.2', '入门学徒'],
    [0.55, 'Lv.3', '熟练玩家'],
    [0.80, 'Lv.4', 'AI 高手'],
    [9.99, 'Lv.5', '提示词大师']
  ]

  function refresh() {
    let xp = 0
    nodes.forEach((n) => {
      const on = lit.has(n.getAttribute('data-skill'))
      n.classList.toggle('is-lit', on)
      if (on) xp += Number(n.getAttribute('data-xp')) || 10
    })
    const ratio = totalXp ? xp / totalXp : 0
    const tier = TIERS.find((t) => ratio < t[0]) || TIERS[TIERS.length - 1]
    if (lvEl) lvEl.textContent = tier[1]
    if (lvNameEl) lvNameEl.textContent = tier[2]
    if (countEl) countEl.textContent = lit.size + ' / ' + nodes.length
    if (xpEl) xpEl.textContent = xp + ' XP'
    if (barEl) barEl.style.width = Math.round(ratio * 100) + '%'
  }

  nodes.forEach((n) => {
    const dot = n.querySelector('.cl-st-dot')
    if (!dot) return
    dot.addEventListener('click', (e) => {
      e.preventDefault()
      e.stopPropagation()
      const id = n.getAttribute('data-skill')
      if (lit.has(id)) lit.delete(id)
      else { lit.add(id); pulse(n) }
      lsSet(K_ST, Array.from(lit))
      refresh()
    })
  })

  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      if (!window.confirm('确定要清空技能树的所有进度吗？')) return
      lit.clear()
      lsSet(K_ST, [])
      refresh()
    })
  }

  refresh()
}

/* ---------- 入口 ---------- */
export function installBoards() {
  if (typeof document === 'undefined') return
  if (document.documentElement.classList.contains('js-boards-ready')) return
  document.documentElement.classList.add('js-boards-ready')

  const run = () => {
    if (document.querySelector('.cl-te')) installTimeEngine(document)
    if (document.getElementById('cl-bb-pool')) installBlindBox(document)
    if (document.querySelector('.cl-st')) installSkillTree(document)
  }

  run()
  // 站内整页跳转后重新绑定（VitePress 路由切换）
  window.addEventListener('click', () => setTimeout(run, 260), true)
}

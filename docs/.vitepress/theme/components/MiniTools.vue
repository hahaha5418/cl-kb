<template>
  <div class="cl-tools">
    <div class="cl-tools-tabs">
      <button
        v-for="t in tabs"
        :key="t.key"
        :class="['cl-tools-tab', { active: tab === t.key }]"
        @click="tab = t.key"
      >{{ t.icon }} {{ t.label }}</button>
    </div>

    <!-- 计算器 -->
    <section v-show="tab === 'calc'" class="cl-tool-panel">
      <div class="cl-calc-screen">
        <div class="cl-calc-expr">{{ calcExpr || '0' }}</div>
        <div class="cl-calc-res">{{ calcRes }}</div>
      </div>
      <div class="cl-calc-grid">
        <button class="cl-calc-key op" @click="calcInput('C')">C</button>
        <button class="cl-calc-key op" @click="calcInput('⌫')">⌫</button>
        <button class="cl-calc-key op" @click="calcInput('%')">%</button>
        <button class="cl-calc-key op" @click="calcInput('/')">÷</button>

        <button class="cl-calc-key" @click="calcInput('7')">7</button>
        <button class="cl-calc-key" @click="calcInput('8')">8</button>
        <button class="cl-calc-key" @click="calcInput('9')">9</button>
        <button class="cl-calc-key op" @click="calcInput('*')">×</button>

        <button class="cl-calc-key" @click="calcInput('4')">4</button>
        <button class="cl-calc-key" @click="calcInput('5')">5</button>
        <button class="cl-calc-key" @click="calcInput('6')">6</button>
        <button class="cl-calc-key op" @click="calcInput('-')">−</button>

        <button class="cl-calc-key" @click="calcInput('1')">1</button>
        <button class="cl-calc-key" @click="calcInput('2')">2</button>
        <button class="cl-calc-key" @click="calcInput('3')">3</button>
        <button class="cl-calc-key op" @click="calcInput('+')">+</button>

        <button class="cl-calc-key wide" @click="calcInput('0')">0</button>
        <button class="cl-calc-key" @click="calcInput('.')">.</button>
        <button class="cl-calc-key" @click="calcInput('(')">(</button>
        <button class="cl-calc-key" @click="calcInput(')')">)</button>
        <button class="cl-calc-key eq wide" @click="calcInput('=')">=</button>
      </div>
      <p class="cl-tool-tip">支持 + − × ÷ % 和括号，纯浏览器计算，不上传任何数据。</p>
    </section>

    <!-- 颜色提取器 -->
    <section v-show="tab === 'color'" class="cl-tool-panel">
      <div class="cl-color-main">
        <input v-model="color" class="cl-color-input" type="color" />
        <div class="cl-color-vals">
          <div class="cl-color-row"><span>HEX</span><code>{{ color.toUpperCase() }}</code><button @click="copy(color.toUpperCase())">复制</button></div>
          <div class="cl-color-row"><span>RGB</span><code>{{ rgb }}</code><button @click="copy(rgb)">复制</button></div>
          <div class="cl-color-row"><span>HSL</span><code>{{ hsl }}</code><button @click="copy(hsl)">复制</button></div>
        </div>
      </div>

      <div class="cl-color-palette">
        <div
          v-for="(c, i) in shades"
          :key="i"
          class="cl-color-chip"
          :style="{ background: c }"
          :title="c.toUpperCase()"
          @click="color = c; copy(c.toUpperCase())"
        >{{ c.toUpperCase() }}</div>
      </div>

      <div class="cl-color-actions">
        <button v-if="hasEyeDropper" class="cl-btn" @click="useEyeDropper">🎯 用系统取色器取色</button>
        <label class="cl-btn cl-btn-file">
          🖼️ 上传图片取色
          <input type="file" accept="image/*" @change="onImg" hidden />
        </label>
      </div>
      <canvas
        v-show="imgSrc"
        ref="canvas"
        class="cl-color-canvas"
        @click="pickPixel"
      ></canvas>
      <p class="cl-tool-tip">点色块即可复制；上传图片后点图中任意位置取色。</p>
    </section>

    <!-- 待办清单 -->
    <section v-show="tab === 'todo'" class="cl-tool-panel">
      <div class="cl-todo-add">
        <input
          v-model="todoInput"
          class="cl-todo-input"
          type="text"
          placeholder="写点要做的事，回车添加…"
          @keydown.enter="addTodo"
        />
        <button class="cl-btn" @click="addTodo">添加</button>
      </div>
      <ul class="cl-todo-list">
        <li v-for="t in todos" :key="t.id" :class="{ done: t.done }">
          <label>
            <input type="checkbox" :checked="t.done" @change="toggleTodo(t)" />
            <span>{{ t.text }}</span>
          </label>
          <button class="cl-todo-del" title="删除" @click="delTodo(t)">✕</button>
        </li>
      </ul>
      <div class="cl-todo-foot">
        <span>共 {{ todos.length }} 项，已完成 {{ todos.filter((t) => t.done).length }} 项</span>
        <button class="cl-btn-link" @click="clearDone">清除已完成</button>
      </div>
      <p class="cl-tool-tip">清单保存在你本机浏览器（localStorage），不会上传到任何服务器。</p>
    </section>

    <!-- 文本加密 -->
    <section v-show="tab === 'cipher'" class="cl-tool-panel">
      <div class="cl-cipher-field">
        <label>密码（解密时必须一致）</label>
        <input v-model="cipherPass" class="cl-todo-input" type="password" placeholder="设一个密码" />
      </div>
      <div class="cl-cipher-field">
        <label>原文 / 密文</label>
        <textarea v-model="cipherText" class="cl-cipher-area" rows="4" placeholder="输入要加密或解密的文字…"></textarea>
      </div>
      <div class="cl-cipher-btns">
        <button class="cl-btn" :disabled="busy" @click="doEncrypt">🔒 加密</button>
        <button class="cl-btn" :disabled="busy" @click="doDecrypt">🔓 解密</button>
        <button class="cl-btn-link" @click="cipherOut = ''; cipherText = ''">清空</button>
      </div>
      <div v-if="cipherOut" class="cl-cipher-out">
        <label>结果（已用 Base64 编码，直接复制保存）</label>
        <textarea class="cl-cipher-area" rows="4" readonly :value="cipherOut"></textarea>
        <button class="cl-btn" @click="copy(cipherOut)">复制结果</button>
      </div>
      <p v-if="cipherErr" class="cl-cipher-err">⚠️ {{ cipherErr }}</p>
      <p class="cl-tool-tip">使用浏览器内置的 AES-GCM 加密（256 位），全程本地完成，不上网。</p>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const tab = ref('calc')
const tabs = [
  { key: 'calc', label: '计算器', icon: '🧮' },
  { key: 'color', label: '颜色提取器', icon: '🎨' },
  { key: 'todo', label: '待办清单', icon: '✅' },
  { key: 'cipher', label: '文本加密', icon: '🔐' }
]

/* ---------- 计算器 ---------- */
const calcExpr = ref('')
const calcRes = ref('')
function calcInput(v) {
  if (v === 'C') { calcExpr.value = ''; calcRes.value = ''; return }
  if (v === '⌫') { calcExpr.value = calcExpr.value.slice(0, -1); calcRes.value = ''; return }
  if (v === '=') {
    try {
      const e = calcExpr.value.replace(/[^0-9+\-*/().% ]/g, '')
      if (!e) { calcRes.value = ''; return }
      // eslint-disable-next-line no-new-func
      calcRes.value = String(Function('"use strict";return (' + e + ')')())
    } catch (e) {
      calcRes.value = '错误'
    }
    return
  }
  calcExpr.value += v
}

/* ---------- 颜色提取器 ---------- */
const color = ref('#4f46e5')
const hasEyeDropper = typeof window !== 'undefined' && 'EyeDropper' in window

function hexToRgb(hex) {
  const h = hex.replace('#', '')
  const n = parseInt(h.length === 3 ? h.split('').map((c) => c + c).join('') : h, 16)
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 }
}
function rgbToHex(r, g, b) {
  const c = (x) => Math.max(0, Math.min(255, Math.round(x))).toString(16).padStart(2, '0')
  return '#' + c(r) + c(g) + c(b)
}
function rgbToHsl(r, g, b) {
  r /= 255; g /= 255; b /= 255
  const max = Math.max(r, g, b), min = Math.min(r, g, b)
  let h = 0, s = 0; const l = (max + min) / 2
  if (max !== min) {
    const d = max - min
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
    if (max === r) h = (g - b) / d + (g < b ? 6 : 0)
    else if (max === g) h = (b - r) / d + 2
    else h = (r - g) / d + 4
    h /= 6
  }
  return `${Math.round(h * 360)}°, ${Math.round(s * 100)}%, ${Math.round(l * 100)}%`
}
const rgb = computed(() => {
  const { r, g, b } = hexToRgb(color.value)
  return `rgb(${r}, ${g}, ${b})`
})
const hsl = computed(() => {
  const { r, g, b } = hexToRgb(color.value)
  return rgbToHsl(r, g, b)
})
const shades = computed(() => {
  const { r, g, b } = hexToRgb(color.value)
  const out = []
  for (const amt of [-0.3, -0.15, 0, 0.15, 0.3]) {
    if (amt === 0) { out.push(color.value); continue }
    if (amt < 0) {
      const k = 1 + amt
      out.push(rgbToHex(r * k, g * k, b * k))
    } else {
      out.push(rgbToHex(r + (255 - r) * amt, g + (255 - g) * amt, b + (255 - b) * amt))
    }
  }
  return out
})
function copy(v) {
  if (navigator.clipboard) navigator.clipboard.writeText(v).catch(() => {})
}
async function useEyeDropper() {
  try {
    const ed = new window.EyeDropper()
    const res = await ed.open()
    color.value = res.sRGBHex
  } catch (e) { /* 用户取消 */ }
}
const canvas = ref(null)
const imgSrc = ref('')
function onImg(e) {
  const file = e.target.files[0]
  if (!file) return
  const url = URL.createObjectURL(file)
  imgSrc.value = url
  const img = new Image()
  img.onload = () => {
    const cv = canvas.value
    if (!cv) return
    const max = 360
    const scale = Math.min(1, max / Math.max(img.width, img.height))
    cv.width = img.width * scale
    cv.height = img.height * scale
    cv.getContext('2d').drawImage(img, 0, 0, cv.width, cv.height)
  }
  img.src = url
}
function pickPixel(e) {
  const cv = canvas.value
  if (!cv) return
  const rect = cv.getBoundingClientRect()
  const x = (e.clientX - rect.left) * (cv.width / rect.width)
  const y = (e.clientY - rect.top) * (cv.height / rect.height)
  const d = cv.getContext('2d').getImageData(x, y, 1, 1).data
  color.value = rgbToHex(d[0], d[1], d[2])
}

/* ---------- 待办清单 ---------- */
const todos = ref([])
const todoInput = ref('')
const TODO_KEY = 'cl_todos'
onMounted(() => {
  try {
    const raw = localStorage.getItem(TODO_KEY)
    if (raw) todos.value = JSON.parse(raw)
  } catch (e) {}
})
function saveTodos() {
  try { localStorage.setItem(TODO_KEY, JSON.stringify(todos.value)) } catch (e) {}
}
function addTodo() {
  const t = todoInput.value.trim()
  if (!t) return
  todos.value.push({ id: Date.now(), text: t, done: false })
  todoInput.value = ''
  saveTodos()
}
function toggleTodo(t) { t.done = !t.done; saveTodos() }
function delTodo(t) { todos.value = todos.value.filter((x) => x !== t); saveTodos() }
function clearDone() { todos.value = todos.value.filter((t) => !t.done); saveTodos() }

/* ---------- 文本加密（AES-GCM / Web Crypto） ---------- */
const cipherPass = ref('')
const cipherText = ref('')
const cipherOut = ref('')
const cipherErr = ref('')
const busy = ref(false)

function bufToB64(buf) {
  const b = new Uint8Array(buf)
  let s = ''
  for (const x of b) s += String.fromCharCode(x)
  return btoa(s)
}
function b64ToBuf(b64) {
  const s = atob(b64)
  const u = new Uint8Array(s.length)
  for (let i = 0; i < s.length; i++) u[i] = s.charCodeAt(i)
  return u.buffer
}
async function deriveKey(pass, salt) {
  const enc = new TextEncoder()
  const mat = await crypto.subtle.importKey('raw', enc.encode(pass), 'PBKDF2', false, ['deriveKey'])
  return crypto.subtle.deriveKey(
    { name: 'PBKDF2', salt, iterations: 100000, hash: 'SHA-256' },
    mat,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt']
  )
}
async function doEncrypt() {
  cipherErr.value = ''
  if (!cipherPass.value) { cipherErr.value = '请先填密码'; return }
  busy.value = true
  try {
    const salt = crypto.getRandomValues(new Uint8Array(16))
    const iv = crypto.getRandomValues(new Uint8Array(12))
    const key = await deriveKey(cipherPass.value, salt)
    const ct = await crypto.subtle.encrypt(
      { name: 'AES-GCM', iv }, key, new TextEncoder().encode(cipherText.value)
    )
    cipherOut.value = bufToB64(salt) + ':' + bufToB64(iv) + ':' + bufToB64(ct)
  } catch (e) {
    cipherErr.value = '加密失败：' + e.message
  } finally { busy.value = false }
}
async function doDecrypt() {
  cipherErr.value = ''
  if (!cipherPass.value) { cipherErr.value = '请先填密码'; return }
  busy.value = true
  try {
    const parts = cipherText.value.trim().split(':')
    if (parts.length !== 3) { cipherErr.value = '密文格式不对（应为 盐:IV:密文）'; return }
    const salt = new Uint8Array(b64ToBuf(parts[0]))
    const iv = new Uint8Array(b64ToBuf(parts[1]))
    const ct = b64ToBuf(parts[2])
    const key = await deriveKey(cipherPass.value, salt)
    const pt = await crypto.subtle.decrypt({ name: 'AES-GCM', iv }, key, ct)
    cipherOut.value = new TextDecoder().decode(pt)
  } catch (e) {
    cipherErr.value = '解密失败：密码错误或密文损坏'
  } finally { busy.value = false }
}
</script>

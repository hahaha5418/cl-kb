<script setup>
import { ref, nextTick, onMounted } from 'vue'

const open = ref(false)
const input = ref('')
const loading = ref(false)
const messages = ref([])
const listEl = ref(null)

const HISTORY_KEY = 'cl-ai-chat'
const SUGGEST = ['什么是 RAG？', '零基础怎么学 AI？', '推荐今天的学习路径', 'diffusion 模型是干嘛的？']

onMounted(() => {
  try {
    const h = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]')
    if (Array.isArray(h)) messages.value = h.slice(-12)
  } catch {}
})

function save() {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(messages.value.slice(-20)))
  } catch {}
}

async function send(text) {
  const q = (text ?? input.value).trim()
  if (!q || loading.value) return
  input.value = ''
  messages.value.push({ role: 'user', text: q })
  messages.value.push({ role: 'bot', text: '思考中…', refs: [] })
  loading.value = true
  await nextTick()
  scroll()
  try {
    const res = await fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ q }),
    })
    const data = await res.json()
    const last = messages.value[messages.value.length - 1]
    if (!res.ok) {
      last.text = '⚠️ ' + (data.error || '服务暂不可用。\n（当前为 WorkBuddy 静态版时，AI 助手仅在 Vercel 链接上可用）')
    } else {
      last.text = data.answer || '（无内容）'
      last.refs = data.refs || []
    }
  } catch (e) {
    const last = messages.value[messages.value.length - 1]
    last.text = '⚠️ 网络错误，请稍后重试。\n（AI 助手需在支持 Serverless 的 Vercel 链接上使用）'
  } finally {
    loading.value = false
    save()
    await nextTick()
    scroll()
  }
}

function scroll() {
  if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight
}

function onKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

function close() {
  open.value = false
}
</script>

<template>
  <div class="ai-fab-wrap">
    <transition name="ai-pop">
      <div v-if="open" class="ai-panel" role="dialog" aria-label="AI 助手">
        <header class="ai-head">
          <span class="ai-dot" /> <b>CL 知识库 · AI 助手</b>
          <button class="ai-x" @click="close" aria-label="关闭">×</button>
        </header>

        <div ref="listEl" class="ai-list">
          <p v-if="!messages.length" class="ai-empty">
            问我任何关于这个网站知识库的问题 👇<br />
            <span class="ai-sug" v-for="s in SUGGEST" :key="s" @click="send(s)">{{ s }}</span>
          </p>
          <div
            v-for="(m, i) in messages"
            :key="i"
            class="ai-msg"
            :class="m.role === 'user' ? 'ai-me' : 'ai-bot'"
          >
            <div class="ai-bubble" v-text="m.text"></div>
            <div v-if="m.refs && m.refs.length" class="ai-refs">
              <a v-for="(r, j) in m.refs" :key="j" :href="r.url" class="ai-ref">📎 {{ r.title }}</a>
            </div>
          </div>
        </div>

        <footer class="ai-foot">
          <textarea
            v-model="input"
            class="ai-input"
            rows="1"
            placeholder="输入问题，回车发送…"
            @keydown="onKey"
          ></textarea>
          <button class="ai-send" :disabled="loading" @click="send">发送</button>
        </footer>
      </div>
    </transition>

    <button class="ai-fab" :class="{ 'ai-fab-on': open }" @click="open = !open" aria-label="打开 AI 助手">
      <span v-if="!open">🤖</span>
      <span v-else>×</span>
    </button>
  </div>
</template>

<style scoped>
.ai-fab-wrap {
  position: fixed;
  right: 20px;
  bottom: 22px;
  z-index: 200;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 12px;
}
.ai-fab {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  border: none;
  cursor: pointer;
  font-size: 24px;
  color: #fff;
  background: linear-gradient(120deg, #8b5cf6, #22d3ee);
  box-shadow: 0 8px 24px rgba(124, 58, 237, 0.45);
  transition: transform 0.18s ease, box-shadow 0.18s ease;
  -webkit-tap-highlight-color: transparent;
}
.ai-fab:active { transform: scale(0.92); }
.ai-fab.ai-fab-on { background: linear-gradient(120deg, #ec4899, #8b5cf6); }

.ai-panel {
  width: 340px;
  max-width: calc(100vw - 28px);
  height: 520px;
  max-height: calc(100vh - 120px);
  background: rgba(18, 18, 30, 0.96);
  border: 1px solid #2a2a3e;
  border-radius: 18px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  backdrop-filter: blur(12px);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}
.ai-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  border-bottom: 1px solid #23233a;
  color: #ECECF5;
  font-size: 14px;
}
.ai-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: #22d3ee; box-shadow: 0 0 8px #22d3ee;
}
.ai-x {
  margin-left: auto; background: none; border: none; color: #A6A6C2;
  font-size: 20px; cursor: pointer; line-height: 1;
}
.ai-list { flex: 1; overflow-y: auto; padding: 14px; display: flex; flex-direction: column; gap: 12px; -webkit-overflow-scrolling: touch; }
.ai-empty { color: #6E6E8C; font-size: 13px; line-height: 1.8; }
.ai-sug {
  display: inline-block; margin: 4px 6px 0 0; padding: 4px 10px;
  border: 1px solid #2a2a3e; border-radius: 999px; color: #a78bfa;
  font-size: 12px; cursor: pointer;
}
.ai-sug:active { background: rgba(139, 92, 246, 0.2); }
.ai-msg { display: flex; flex-direction: column; max-width: 88%; }
.ai-me { align-self: flex-end; align-items: flex-end; }
.ai-bot { align-self: flex-start; }
.ai-bubble {
  padding: 9px 12px; border-radius: 14px; font-size: 13.5px; line-height: 1.6;
  white-space: pre-wrap; word-break: break-word;
}
.ai-me .ai-bubble { background: linear-gradient(120deg, #8b5cf6, #6366f1); color: #fff; border-bottom-right-radius: 4px; }
.ai-bot .ai-bubble { background: #1c1c2a; color: #ECECF5; border-bottom-left-radius: 4px; }
.ai-refs { margin-top: 6px; display: flex; flex-direction: column; gap: 4px; }
.ai-ref { color: #22d3ee; font-size: 12px; text-decoration: none; }
.ai-ref:hover { text-decoration: underline; }
.ai-foot { display: flex; gap: 8px; padding: 10px; border-top: 1px solid #23233a; }
.ai-input {
  flex: 1; resize: none; background: #12121e; border: 1px solid #2a2a3e;
  border-radius: 10px; color: #ECECF5; padding: 9px 11px; font-size: 13.5px;
  font-family: inherit; max-height: 90px;
}
.ai-input:focus { outline: none; border-color: #8b5cf6; }
.ai-send {
  border: none; border-radius: 10px; padding: 0 16px; cursor: pointer;
  background: linear-gradient(120deg, #8b5cf6, #22d3ee); color: #fff; font-size: 13.5px;
}
.ai-send:disabled { opacity: 0.5; cursor: default; }

.ai-pop-enter-active, .ai-pop-leave-active { transition: transform 0.2s ease, opacity 0.2s ease; }
.ai-pop-enter-from, .ai-pop-leave-to { transform: translateY(10px) scale(0.96); opacity: 0; }

/* 移动端：面板变底部抽屉，卡片顺滑 */
@media (max-width: 640px) {
  .ai-fab-wrap { right: 14px; bottom: 16px; }
  .ai-panel {
    width: 100vw; max-width: 100vw; height: 72vh; max-height: 72vh;
    border-radius: 18px 18px 0 0; position: fixed; right: 0; bottom: 0;
  }
}
</style>

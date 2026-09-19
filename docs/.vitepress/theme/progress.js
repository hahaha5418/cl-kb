// 学习打卡进度：用 localStorage 记录用户在「学习路径」里标记完成的步骤。
// 数据只存在用户自己浏览器里，不联网、不上传，换设备不共享（符合零基础用户的简单预期）。
import { reactive } from 'vue'

export const PROGRESS_KEY = 'cl-kb-progress-v1'

// 唯一数据源：steps 的 key 是页面 relativePath（如 path/stage-1/01-xxx.md），value 是完成时间戳
export const progressState = reactive({ steps: {} })

let loaded = false
// 仅在浏览器端（onMounted）调用一次，避免 SSR 水合不一致
export function loadProgress() {
  if (loaded) return
  loaded = true
  try {
    if (typeof localStorage !== 'undefined') {
      const raw = localStorage.getItem(PROGRESS_KEY)
      const obj = raw ? JSON.parse(raw) : {}
      progressState.steps = obj.steps || {}
    }
  } catch (e) {
    /* 坏数据忽略，不影响页面 */
  }
}

export function isDone(id) {
  return !!progressState.steps[id]
}

export function toggleStep(id) {
  if (progressState.steps[id]) delete progressState.steps[id]
  else progressState.steps[id] = Date.now()
  persist()
  return isDone(id)
}

export function resetProgress() {
  progressState.steps = {}
  persist()
}

function persist() {
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(PROGRESS_KEY, JSON.stringify({ steps: progressState.steps }))
    }
  } catch (e) {
    /* 隐私模式等写不进时忽略 */
  }
}

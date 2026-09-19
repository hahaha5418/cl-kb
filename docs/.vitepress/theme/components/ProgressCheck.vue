<!-- 学习路径每一步底部的「打卡」按钮：标记/取消完成，进度写入 localStorage -->
<template>
  <div v-if="visible" class="cl-check">
    <button :class="['cl-check-btn', { on: done }]" @click="click">
      {{ done ? '✅ 我已完成这一步' : '○ 标记这一步已完成' }}
    </button>
    <span class="cl-check-tip">进度只保存在你这台设备的浏览器里，不会上传</span>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useData } from 'vitepress'
import { progressState, loadProgress, toggleStep } from '../progress'

const { page } = useData()
// relativePath 形如 path/stage-1/01-xxx.md，天然唯一稳定，直接当 id
const id = computed(() => page.value.relativePath)
// 只在「学习路径」下的页面显示打卡按钮
const visible = computed(() => id.value.startsWith('path/'))
const done = computed(() => !!progressState.steps[id.value])

onMounted(() => loadProgress())

function click() {
  toggleStep(id.value)
}
</script>

<style>
.cl-check {
  margin: 30px 0 6px;
  display: flex;
  flex-direction: column;
  gap: 7px;
  align-items: flex-start;
}
.cl-check-btn {
  border: 1px solid var(--vp-c-brand-1);
  background: transparent;
  color: var(--vp-c-brand-1);
  border-radius: 10px;
  padding: 10px 18px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all .15s;
}
.cl-check-btn:hover { background: rgba(139, 92, 246, .12); }
.cl-check-btn.on {
  background: var(--vp-c-brand-1);
  color: #fff;
  box-shadow: 0 4px 14px rgba(139, 92, 246, .35);
}
.cl-check-tip { font-size: 12px; color: var(--vp-c-text-2); }
</style>

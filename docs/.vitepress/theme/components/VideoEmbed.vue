<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  platform: { type: String, default: 'bilibili' }, // bilibili | youtube
  bvid: { type: String, default: '' },              // 哔哩哔哩 BV 号
  id: { type: String, default: '' },                // YouTube 视频 id
  title: { type: String, default: '视频' }
})

const wrapper = ref(null)
const loaded = ref(false)
let observer = null

function embedSrc() {
  if (props.platform === 'youtube') {
    return props.id ? `https://www.youtube.com/embed/${props.id}` : ''
  }
  return props.bvid
    ? `https://player.bilibili.com/player.html?bvid=${props.bvid}&page=1&high_quality=1&danmaku=0`
    : ''
}

function ensure() {
  if (loaded.value) return
  loaded.value = true
}

onMounted(() => {
  if (!wrapper.value) return
  // 懒加载：滚动到附近才真正加载 iframe，省流量、防卡顿
  observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          ensure()
          observer && observer.disconnect()
        }
      })
    },
    { rootMargin: '240px' }
  )
  observer.observe(wrapper.value)
})
onBeforeUnmount(() => observer && observer.disconnect())
</script>

<template>
  <div class="cl-video" ref="wrapper">
    <iframe
      v-if="loaded && embedSrc()"
      :src="embedSrc()"
      :title="title"
      frameborder="0"
      allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
      allowfullscreen
      loading="lazy"
    ></iframe>
    <div v-else class="cl-video-ph">
      <span class="cl-play">▶</span>
      <span class="cl-video-tip">
        滚动到这里自动加载视频（{{ platform === 'bilibili' ? '哔哩哔哩' : 'YouTube' }}）
      </span>
    </div>
  </div>
</template>

<style scoped>
.cl-video {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  border-radius: 14px;
  overflow: hidden;
  border: 1px solid var(--vp-c-border);
  background: linear-gradient(135deg, rgba(124, 58, 237, 0.25), rgba(34, 211, 238, 0.15));
  margin: 18px 0;
}
.cl-video iframe {
  width: 100%;
  height: 100%;
  border: 0;
  display: block;
}
.cl-video-ph {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #fff;
}
.cl-play {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
}
.cl-video-tip {
  font-size: 0.82rem;
  opacity: 0.85;
}
</style>

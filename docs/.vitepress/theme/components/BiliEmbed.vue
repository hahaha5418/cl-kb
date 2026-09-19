<script setup>
import { computed } from 'vue'

const props = defineProps({
  url: { type: String, default: '' },
  bvid: { type: String, default: '' },
  page: { type: Number, default: 1 },
  title: { type: String, default: 'B 站视频' }
})

// 从各种 B 站链接里抠出视频号（BVxxxx 或 av 号），纯前端、不联网
function extractId(s) {
  if (!s) return ''
  s = String(s).trim()
  let m = s.match(/BV[0-9A-Za-z]+/)
  if (m) return m[0]
  m = s.match(/[?&]bvid=(BV[0-9A-Za-z]+)/)
  if (m) return m[1]
  m = s.match(/bilibili\.com\/video\/(av\d+)/i)
  if (m) return m[1]
  return ''
}

const src = computed(() => {
  const id = extractId(props.url) || extractId(props.bvid)
  if (!id) return ''
  const p = new URLSearchParams({
    bvid: id,
    page: String(props.page || 1),
    high_quality: '1',
    danmaku: '0',
    autoplay: '0'
  })
  return 'https://player.bilibili.com/player.html?' + p.toString()
})
</script>

<template>
  <figure class="cl-bili">
    <div class="cl-bili-frame">
      <iframe
        v-if="src"
        :src="src"
        scrolling="no"
        border="0"
        frameborder="no"
        framespacing="0"
        allowfullscreen="true"
        loading="lazy"
        :title="title"
      ></iframe>
      <div v-else class="cl-bili-empty">
        <p>⚠️ 视频链接无法识别</p>
        <p class="cl-bili-hint">
          请在组件的 <code>url</code> 里填写完整的 B 站视频地址，例如：<br>
          https://www.bilibili.com/video/BV1xx411c7mD
        </p>
      </div>
    </div>
    <figcaption v-if="title && src" class="cl-bili-cap">▶ {{ title }}</figcaption>
  </figure>
</template>

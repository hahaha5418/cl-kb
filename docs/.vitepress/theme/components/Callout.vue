<script setup>
defineProps({
  type: { type: String, default: 'tip' }, // tip | warn | danger | info
  title: { type: String, default: '' }
})
</script>

<template>
  <div class="cl-callout" :class="'cl-callout-' + type">
    <div class="cl-callout-ico">
      <template v-if="type === 'warn'">⚠️</template>
      <template v-else-if="type === 'danger'">🚫</template>
      <template v-else-if="type === 'info'">💡</template>
      <template v-else>✅</template>
    </div>
    <div class="cl-callout-body">
      <div class="cl-callout-title" v-if="title">{{ title }}</div>
      <div class="cl-callout-content"><slot /></div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, default: '' }
})
</script>

<template>
  <div class="cl-step">
    <div class="cl-step-badge"></div>
    <div class="cl-step-body">
      <div class="cl-step-title" v-if="title">{{ title }}</div>
      <div class="cl-step-desc"><slot /></div>
    </div>
  </div>
</template>

<template>
  <div v-if="src" class="auth-image-wrapper">
    <img
      :src="src"
      :alt="alt"
      :class="imgClass"
      :title="alt || '点击查看大图'"
      @click="previewVisible = true"
    />
    <div
      v-if="previewVisible"
      class="image-preview-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="图片预览"
      @click="previewVisible = false"
    >
      <img :src="src" :alt="alt" class="image-preview-img" />
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  url: { type: String, default: '' },
  alt: { type: String, default: '图片' },
  imgClass: { type: String, default: 'chat-msg-image' },
})

const src = ref('')
const previewVisible = ref(false)
let objectUrl = ''

async function load() {
  if (objectUrl) {
    URL.revokeObjectURL(objectUrl)
    objectUrl = ''
  }
  src.value = ''
  previewVisible.value = false
  if (!props.url) return
  const token = localStorage.getItem('access_token')
  try {
    const res = await fetch(props.url, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!res.ok) return
    const blob = await res.blob()
    objectUrl = URL.createObjectURL(blob)
    src.value = objectUrl
  } catch {
    src.value = ''
  }
}

function onKeydown(e) {
  if (e.key === 'Escape') previewVisible.value = false
}

watch(() => props.url, load, { immediate: true })
watch(previewVisible, (v) => {
  document.body.style.overflow = v ? 'hidden' : ''
  if (v) {
    window.addEventListener('keydown', onKeydown)
  } else {
    window.removeEventListener('keydown', onKeydown)
  }
})

onBeforeUnmount(() => {
  if (objectUrl) URL.revokeObjectURL(objectUrl)
  window.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
})
</script>

<style scoped>
.auth-image-wrapper {
  display: inline-block;
}
.image-preview-overlay {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.72);
  cursor: zoom-out;
  padding: 24px;
}
.image-preview-img {
  max-width: 90vw;
  max-height: 90vh;
  object-fit: contain;
  border-radius: 8px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.35);
  cursor: default;
  background: #fff;
}
</style>

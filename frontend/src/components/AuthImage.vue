<template>
  <img v-if="src" :src="src" :alt="alt" :class="imgClass" />
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  url: { type: String, default: '' },
  alt: { type: String, default: '图片' },
  imgClass: { type: String, default: 'chat-msg-image' },
})

const src = ref('')
let objectUrl = ''

async function load() {
  if (objectUrl) {
    URL.revokeObjectURL(objectUrl)
    objectUrl = ''
  }
  src.value = ''
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

watch(() => props.url, load, { immediate: true })

onBeforeUnmount(() => {
  if (objectUrl) URL.revokeObjectURL(objectUrl)
})
</script>

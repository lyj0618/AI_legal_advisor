<template>
  <router-view />
</template>

<script setup>
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'

const store = useAppStore()
const auth = useAuthStore()
const route = useRoute()

onMounted(async () => {
  auth.restore()
  if (auth.isLoggedIn && route.name !== 'login') {
    if (!auth.role) await auth.fetchMe()
    await store.init(auth.isAdmin, auth.username)
  }
})
</script>

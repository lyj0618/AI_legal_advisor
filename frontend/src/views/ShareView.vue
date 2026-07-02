<template>
  <div class="share-page">
    <div class="share-card">
      <h2>{{ data?.name || '咨询记录' }}</h2>
      <p style="font-size:12px;color:#94a3b8;">只读分享 · 仅供参考</p>
      <div v-for="(m, i) in data?.messages || []" :key="i" class="share-msg" :class="m.role">
        <div class="share-role">{{ m.role === 'user' ? '用户' : '助手' }}</div>
        <div class="share-content">
          <AnswerContent v-if="m.role === 'assistant'" :text="m.content" />
          <span v-else>{{ m.content }}</span>
        </div>
      </div>
      <el-empty v-if="!loading && !(data?.messages || []).length" description="暂无内容或链接已失效" />
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/api'
import AnswerContent from '@/components/AnswerContent.vue'

const route = useRoute()
const loading = ref(true)
const data = ref(null)

onMounted(async () => {
  try {
    data.value = await api.getSharedChat(route.params.token)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.share-page {
  min-height: 100vh;
  background: #f8fafc;
  padding: 32px 16px;
}
.share-card {
  max-width: 760px;
  margin: 0 auto;
  background: #fff;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 8px 30px rgba(15, 23, 42, 0.08);
}
.share-msg { margin-top: 16px; padding: 12px; border-radius: 10px; }
.share-msg.user { background: #eff6ff; }
.share-msg.assistant { background: #f8fafc; }
.share-role { font-size: 11px; color: #64748b; margin-bottom: 6px; }
.share-content { white-space: pre-wrap; line-height: 1.7; font-size: 14px; }
</style>

<template>
  <div class="center-content">
    <div class="experts-header">
      <h2>法律顾问团</h2>
      <p>选择专业领域的 AI 法律顾问，基于 qwen-turbo 与法律知识库为您提供咨询（仅供参考，不构成正式法律意见）</p>
    </div>
    <el-empty v-if="!store.experts.length" description="暂无可咨询专家，请联系管理员配置并发布已绑定知识库的专家" />
    <div v-else class="experts-grid">
      <div
        v-for="e in store.experts"
        :key="e.id"
        class="expert-card"
        :style="{ '--expert-color': e.color }"
        @click="summon(e)"
      >
        <div class="expert-top">
          <div
            class="expert-avatar"
            :style="{ background: e.color + '14', color: e.color }"
          >
            <img v-if="e.avatarFile && e.avatarFile !== '__chat__'" :src="`/avatars/${e.avatarFile}`" alt="" style="width:57px;height:57px;border-radius:50%;object-fit:cover;" />
            <span v-else>{{ e.name.charAt(0) }}</span>
          </div>
          <div class="expert-name">{{ e.name }}</div>
          <div class="expert-role" :style="{ color: e.color, backgroundColor: e.color + '1f' }">{{ e.role }}</div>
        </div>
        <div class="expert-desc">{{ e.desc }}</div>
        <div class="expert-action">
          <el-button plain style="width:100%" @click.stop="summon(e)">
            <el-icon><Plus /></el-icon> 立即咨询
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAppStore } from '@/stores/app'
import { api } from '@/api'

const store = useAppStore()
const router = useRouter()

onMounted(() => store.fetchExperts())

async function summon(e) {
  try {
    const { session_id } = await api.consultExpert(e.id)
    router.push({ name: 'chatDetail', params: { id: session_id }, query: { tab: 'dialog' } })
  } catch (err) {
    ElMessage.error(err.message || '无法开始咨询')
  }
}
</script>

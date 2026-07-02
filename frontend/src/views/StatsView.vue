<template>
  <div class="center-content">
    <div class="kb-toolbar">
      <div>
        <h2>运营统计</h2>
        <p style="font-size:12px;color:#94a3b8;margin-top:4px;">系统使用与知识库处理概况</p>
      </div>
      <el-button size="small" :loading="loading" @click="load">刷新</el-button>
    </div>

    <div v-loading="loading" class="stats-grid">
      <div class="stat-card" v-for="item in cards" :key="item.label">
        <div class="stat-value">{{ item.value }}</div>
        <div class="stat-label">{{ item.label }}</div>
      </div>
    </div>

    <div class="config-section" style="margin-top:20px;">
      <h4>文档处理状态</h4>
      <div class="status-grid">
        <div class="status-card">
          <div class="status-title">清洗进度</div>
          <div class="status-row">
            <span class="status-tag done">已清洗 {{ cleanStats.done }}</span>
            <span class="status-tag pending">待处理 {{ cleanStats.pending }}</span>
          </div>
          <el-progress
            :percentage="cleanStats.percent"
            :stroke-width="10"
            :color="'#16a34a'"
            style="margin-top:12px;"
          />
        </div>
        <div class="status-card">
          <div class="status-title">分块进度</div>
          <div class="status-row">
            <span class="status-tag done">已完成 {{ chunkStats.done }}</span>
            <span class="status-tag pending">待处理 {{ chunkStats.pending }}</span>
          </div>
          <el-progress
            :percentage="chunkStats.percent"
            :stroke-width="10"
            :color="'#2563eb'"
            style="margin-top:12px;"
          />
        </div>
        <div class="status-card">
          <div class="status-title">知识库类型</div>
          <div class="status-row" style="flex-wrap:wrap;gap:8px;">
            <span class="status-tag type">文档库 {{ kbTypeStats.document }}</span>
            <span class="status-tag type">案例库 {{ kbTypeStats.case }}</span>
            <span v-if="kbTypeStats.other" class="status-tag type">其他 {{ kbTypeStats.other }}</span>
          </div>
        </div>
      </div>
    </div>

    <div class="config-section">
      <h4>最近消息</h4>
      <el-table :data="stats.recent_messages || []" size="small" empty-text="暂无">
        <el-table-column label="角色" width="80">
          <template #default="{ row }">{{ row.role === 'user' ? '用户' : '助手' }}</template>
        </el-table-column>
        <el-table-column prop="preview" label="内容预览" show-overflow-tooltip />
        <el-table-column label="时间" width="180">
          <template #default="{ row }">{{ formatDate(row.create_date) }}</template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '@/api'
import { formatDate } from '@/utils/format'

const loading = ref(false)
const stats = ref({})

const cards = computed(() => [
  { label: '知识库', value: stats.value.datasets ?? 0 },
  { label: '文档', value: stats.value.documents ?? 0 },
  { label: '切片', value: stats.value.chunks ?? 0 },
  { label: '咨询会话', value: stats.value.chat_sessions ?? 0 },
  { label: '助手模板', value: stats.value.expert_templates ?? 0 },
  { label: '消息总数', value: stats.value.messages ?? 0 },
  { label: '用户', value: stats.value.users ?? 0 },
  { label: '咨询用户', value: stats.value.consultants ?? 0 },
])

function parseStatus(map, doneKey = '1') {
  const src = map || {}
  let done = 0
  let pending = 0
  for (const [k, v] of Object.entries(src)) {
    const n = Number(v) || 0
    if (k === doneKey) done += n
    else pending += n
  }
  const total = done + pending
  const percent = total ? Math.round((done / total) * 100) : 0
  return { done, pending, percent }
}

const cleanStats = computed(() => parseStatus(stats.value.doc_clean_status))
const chunkStats = computed(() => parseStatus(stats.value.doc_run_status))

const kbTypeStats = computed(() => {
  const src = stats.value.kb_types || {}
  let document = 0
  let caseCount = 0
  let other = 0
  for (const [k, v] of Object.entries(src)) {
    const n = Number(v) || 0
    if (k === 'legal') document += n
    else if (k === 'case') caseCount += n
    else other += n
  }
  return { document, case: caseCount, other }
})

async function load() {
  loading.value = true
  try {
    stats.value = await api.getStatsDashboard()
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}
.stat-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 18px;
  text-align: center;
}
.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #2563eb;
}
.stat-label {
  margin-top: 6px;
  font-size: 12px;
  color: #64748b;
}
.status-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}
.status-card {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px;
}
.status-title {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 10px;
}
.status-row {
  display: flex;
  gap: 10px;
  align-items: center;
}
.status-tag {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 999px;
}
.status-tag.done {
  background: #dcfce7;
  color: #166534;
}
.status-tag.pending {
  background: #fef3c7;
  color: #b45309;
}
.status-tag.type {
  background: #eff6ff;
  color: #1d4ed8;
}
</style>

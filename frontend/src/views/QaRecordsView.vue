<template>
  <div class="center-content">
    <div class="kb-toolbar">
      <div>
        <h2>问答库</h2>
        <p style="font-size:12px;color:#94a3b8;margin-top:4px;">
          管理用户提问与系统回答；置信度为「高」时相同问题将直接返回缓存答案，「低」时重新生成
        </p>
      </div>
      <div style="display:flex;gap:8px;">
        <el-button :loading="syncing" @click="sync">同步历史对话</el-button>
        <el-button @click="load">刷新</el-button>
      </div>
    </div>

    <div style="margin-bottom:16px;display:flex;gap:12px;flex-wrap:wrap;">
      <el-input
        v-model="keyword"
        placeholder="搜索问题或回答"
        clearable
        style="width:260px;"
        @keyup.enter="search"
      />
      <el-select v-model="confidenceFilter" placeholder="置信度" clearable style="width:140px;" @change="search">
        <el-option label="高（直接回复）" value="high" />
        <el-option label="低（重新生成）" value="low" />
      </el-select>
      <el-button type="primary" @click="search">查询</el-button>
    </div>

    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="question" label="用户提问" min-width="200" show-overflow-tooltip />
      <el-table-column label="系统回答" min-width="220">
        <template #default="{ row }">
          <span class="answer-preview">{{ row.answer }}</span>
        </template>
      </el-table-column>
      <el-table-column label="采纳度" width="100" align="center">
        <template #default="{ row }">
          <el-tag
            v-if="row.feedback === 'like'"
            type="success"
            size="small"
          >已采纳</el-tag>
          <el-tag
            v-else-if="row.feedback === 'dislike'"
            type="danger"
            size="small"
          >未采纳</el-tag>
          <el-tag v-else type="info" size="small">未评价</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="置信度" width="130" align="center">
        <template #default="{ row }">
          <el-select
            v-model="row.confidence"
            size="small"
            style="width:108px;"
            @change="(v) => updateConfidence(row, v)"
          >
            <el-option label="高" value="high" />
            <el-option label="低" value="low" />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column prop="hit_count" label="命中次数" width="90" align="center" />
      <el-table-column label="记录时间" width="180">
        <template #default="{ row }">{{ formatDate(row.create_date) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="openDetail(row)">详情</el-button>
          <el-button link type="danger" size="small" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div style="margin-top:16px;display:flex;justify-content:flex-end;">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="load"
      />
    </div>

    <el-dialog v-model="detailVisible" title="问答详情" width="640px">
      <template v-if="current">
        <p style="font-size:12px;color:#64748b;">用户提问</p>
        <div class="detail-box">{{ current.question }}</div>
        <p style="font-size:12px;color:#64748b;margin-top:12px;">系统回答</p>
        <el-input v-model="editAnswer" type="textarea" :rows="10" />
        <div style="margin-top:12px;display:flex;gap:8px;align-items:center;">
          <span style="font-size:12px;color:#64748b;">置信度</span>
          <el-radio-group v-model="editConfidence">
            <el-radio label="high">高（直接回复）</el-radio>
            <el-radio label="low">低（重新生成）</el-radio>
          </el-radio-group>
        </div>
      </template>
      <template #footer>
        <el-button @click="detailVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveDetail">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'
import { formatDate } from '@/utils/format'
import { unwrapPage } from '@/utils/page'

const loading = ref(false)
const syncing = ref(false)
const saving = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const keyword = ref('')
const confidenceFilter = ref('')
const detailVisible = ref(false)
const current = ref(null)
const editAnswer = ref('')
const editConfidence = ref('low')

onMounted(() => {
  load()
})

async function load() {
  loading.value = true
  try {
    const res = await api.getQaRecords({
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
      confidence: confidenceFilter.value || undefined,
    })
    const { items: rows, total: t } = unwrapPage(res)
    items.value = rows
    total.value = t
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  load()
}

async function sync() {
  syncing.value = true
  try {
    const res = await api.syncQaRecords()
    ElMessage.success(res._message || `已同步 ${res.added || 0} 条`)
    await load()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    syncing.value = false
  }
}

async function updateConfidence(row, value) {
  try {
    await api.updateQaRecord(row.id, { confidence: value })
    ElMessage.success(value === 'high' ? '已设为高置信度，相同问题将直接回复' : '已设为低置信度，将重新生成')
  } catch (e) {
    ElMessage.error(e.message)
    load()
  }
}

function openDetail(row) {
  current.value = row
  editAnswer.value = row.answer
  editConfidence.value = row.confidence || 'low'
  detailVisible.value = true
}

async function saveDetail() {
  if (!current.value) return
  saving.value = true
  try {
    await api.updateQaRecord(current.value.id, {
      answer: editAnswer.value,
      confidence: editConfidence.value,
    })
    ElMessage.success('已保存')
    detailVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm('确定删除该问答记录？', '确认', { type: 'warning' })
    await api.deleteQaRecord(row.id)
    ElMessage.success('已删除')
    await load()
  } catch {
    /* cancel */
  }
}
</script>

<style scoped>
.answer-preview {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-size: 13px;
  color: #475569;
  white-space: pre-wrap;
}
.detail-box {
  background: #f8fafc;
  border-radius: 8px;
  padding: 12px;
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
}
</style>

<template>
  <div class="center-content">
    <div class="kb-toolbar">
      <div>
        <h2>法律知识库</h2>
        <p style="font-size:12px;color:#94a3b8;margin-top:4px;">共 {{ store.kbDatasets.length }} 个知识库 · 支持法规、制度、合同等文档</p>
      </div>
      <el-button type="primary" @click="showCreate = true">
        <el-icon><Plus /></el-icon> 创建知识库
      </el-button>
    </div>

    <div v-loading="store.kbLoading" class="kb-card-grid">
      <div v-for="kb in store.kbDatasets" :key="kb.id" class="kb-card" @click="$router.push(`/kb/${kb.id}`)">
        <div class="kb-card-top-bar" />
        <div class="kb-card-body">
          <h3 style="font-size:15px;margin-bottom:8px;">{{ kb.name }}</h3>
          <p style="font-size:12px;color:#94a3b8;min-height:36px;">{{ kb.description || '暂无描述' }}</p>
          <div style="margin-top:12px;">
            <span class="kb-meta-tag">{{ kb.chunk_method || '通用' }}</span>
            <span class="kb-meta-tag">{{ kb.document_count || 0 }} 文档</span>
          </div>
        </div>
        <div class="kb-card-footer">
          <span>{{ formatDate(kb.create_date).split(' ')[0] }}</span>
          <el-icon style="cursor:pointer;color:#ef4444;" @click.stop="remove(kb)"><Delete /></el-icon>
        </div>
      </div>
      <div v-if="!store.kbLoading && !store.kbDatasets.length" style="grid-column:1/-1;text-align:center;padding:80px;color:#94a3b8;">
        暂无法律知识库，点击右上角创建
      </div>
    </div>

    <el-dialog v-model="showCreate" title="创建法律知识库" width="520px" :close-on-click-modal="false">
      <el-form :model="form" label-width="90px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="例如：劳动法规知识库" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="分块方法">
          <el-select v-model="form.chunk_method" style="width:100%">
            <el-option v-for="m in chunkMethods" :key="m.value" :label="m.label" :value="m.value" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="create">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAppStore } from '@/stores/app'
import { api } from '@/api'
import { formatDate } from '@/utils/format'

const store = useAppStore()
const showCreate = ref(false)
const creating = ref(false)
const form = reactive({ name: '', description: '', chunk_method: 'naive' })

const chunkMethods = [
  { label: 'General 通用', value: 'naive' },
  { label: 'Q&A 问答', value: 'qa' },
  { label: 'Laws 法律', value: 'laws' },
  { label: 'Manual 手册', value: 'manual' },
]

onMounted(() => store.fetchDatasets())

async function create() {
  if (!form.name.trim()) return ElMessage.warning('请输入名称')
  creating.value = true
  try {
    await api.createDataset({ ...form, embedding_model: 'text-embedding-v2' })
    showCreate.value = false
    form.name = ''
    form.description = ''
    await store.fetchDatasets()
    ElMessage.success('创建成功')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    creating.value = false
  }
}

async function remove(kb) {
  try {
    await ElMessageBox.confirm(`确定删除「${kb.name}」？`, '确认', { type: 'warning' })
    await api.deleteDatasets([kb.id])
    await store.fetchDatasets()
    ElMessage.success('已删除')
  } catch {
    /* cancel */
  }
}
</script>

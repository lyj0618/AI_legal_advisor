<template>
  <div class="center-content">
    <div class="kb-toolbar">
      <div>
        <h2>专家管理</h2>
        <p style="font-size:12px;color:#94a3b8;margin-top:4px;">配置助手并绑定知识库；发布后咨询用户可在助手广场看到（模型：qwen-turbo）</p>
      </div>
      <el-button type="primary" @click="showCreate = true">
        <el-icon><Plus /></el-icon> 创建助手
      </el-button>
    </div>

    <el-table :data="chats" v-loading="loading" stripe @row-click="edit" style="cursor:pointer;">
      <el-table-column prop="name" label="名称" min-width="160" />
      <el-table-column label="绑定知识库" min-width="180">
        <template #default="{ row }">
          <span style="color:#2563eb;font-size:12px;">{{ row.kbNames || '未绑定' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="发布" width="100" align="center">
        <template #default="{ row }">
          <el-switch
            :model-value="row.is_published"
            :disabled="!row.kb_ids?.length"
            @change="(v) => togglePublish(row, v)"
            @click.stop
          />
        </template>
      </el-table-column>
      <el-table-column label="专家角色" width="140">
        <template #default="{ row }">{{ row.expert_role || '-' }}</template>
      </el-table-column>
      <el-table-column label="创建时间" width="160">
        <template #default="{ row }">{{ formatDate(row.create_date) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="80">
        <template #default="{ row }">
          <el-button link type="danger" size="small" @click.stop="remove(row)">删除</el-button>
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
        @size-change="() => { page = 1; load() }"
      />
    </div>

    <el-dialog v-model="showCreate" title="创建智能助手" width="480px">
      <el-form label-width="90px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="例如：产品咨询助手" />
        </el-form-item>
        <el-form-item label="专家角色">
          <el-input v-model="form.expert_role" placeholder="显示在专家卡片上" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="绑定知识库">
          <el-checkbox-group v-model="form.kb_ids">
            <el-checkbox v-for="kb in store.kbDatasets" :key="kb.id" :label="kb.id" style="display:block;">
              {{ kb.name }}
            </el-checkbox>
          </el-checkbox-group>
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
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAppStore } from '@/stores/app'
import { api } from '@/api'
import { formatDate } from '@/utils/format'
import { unwrapPage } from '@/utils/page'

const store = useAppStore()
const router = useRouter()
const showCreate = ref(false)
const creating = ref(false)
const loading = ref(false)
const chats = ref([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const form = reactive({ name: '', description: '', expert_role: '', kb_ids: [] })

onMounted(async () => {
  await store.fetchChats()
  await load()
})

async function load() {
  loading.value = true
  try {
    const res = await api.getChats({ page: page.value, page_size: pageSize.value })
    const { items, total: t } = unwrapPage(res)
    if (items.length) {
      chats.value = items.map(mapChatRow)
      total.value = t
    } else if (page.value === 1 && store.chatsList.length) {
      chats.value = store.chatsList.slice(0, pageSize.value).map(mapChatRow)
      total.value = store.chatsList.length
    } else {
      chats.value = []
      total.value = t
    }
  } catch (e) {
    ElMessage.error(e.message || '加载专家列表失败')
    if (page.value === 1 && store.chatsList.length) {
      chats.value = store.chatsList.slice(0, pageSize.value).map(mapChatRow)
      total.value = store.chatsList.length
    }
  } finally {
    loading.value = false
  }
}

function mapChatRow(c) {
  return {
    ...c,
    kb_ids: (c.datasets || []).map((d) => d.id),
    kbNames: (c.datasets || []).map((d) => d.name).join(', '),
    is_published: !!c.is_published,
  }
}

function edit(row) {
  router.push({ name: 'chatDetail', params: { id: row.id }, query: { tab: 'settings' } })
}

async function create() {
  if (!form.name.trim()) return ElMessage.warning('请输入名称')
  creating.value = true
  try {
    const chat = await api.createChat({
      name: form.name,
      description: form.description,
      expert_role: form.expert_role,
      kb_ids: form.kb_ids,
    })
    showCreate.value = false
    form.name = ''
    form.description = ''
    form.expert_role = ''
    form.kb_ids = []
    page.value = 1
    await store.fetchChats()
    await load()
    await store.fetchExperts()
    router.push({ name: 'chatDetail', params: { id: chat.id }, query: { tab: 'dialog' } })
    ElMessage.success('创建成功')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    creating.value = false
  }
}

async function togglePublish(row, published) {
  if (!row.kb_ids?.length) {
    return ElMessage.warning('请先绑定知识库后再发布')
  }
  try {
    await api.updateChat(row.id, { is_published: published })
    row.is_published = published
    await store.fetchExperts()
    ElMessage.success(published ? '已发布' : '已取消发布')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(`删除「${row.name}」？`, '确认', { type: 'warning' })
    await api.deleteChats([row.id])
    await store.fetchChats()
    await load()
    await store.fetchExperts()
    ElMessage.success('已删除')
  } catch {
    /* cancel */
  }
}
</script>

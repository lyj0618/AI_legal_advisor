<template>
  <div class="center-content">
    <div class="experts-header">
      <h2>用户管理</h2>
      <p>创建与管理咨询账号（登录后可使用助手广场与咨询对话）</p>
    </div>

    <el-card shadow="never" style="margin-bottom:20px;">
      <template #header>新建用户</template>
      <el-form :model="form" label-width="90px" style="max-width:480px;">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="3-64 个字符" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password placeholder="至少 6 位" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role" style="width:100%">
            <el-option label="咨询用户（助手广场）" value="consultant" />
            <el-option label="管理员（全部功能）" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="creating" @click="create">创建</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-table :data="users" v-loading="loading" stripe>
      <el-table-column prop="username" label="用户名" />
      <el-table-column prop="role" label="角色" width="120">
        <template #default="{ row }">
          <el-tag :type="row.role === 'admin' ? 'danger' : 'info'" size="small">
            {{ row.role === 'admin' ? '管理员' : '咨询用户' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
            {{ row.is_active ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="180">
        <template #default="{ row }">{{ formatDate(row.create_date) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
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
        @size-change="() => { page = 1; load() }"
      />
    </div>

    <el-dialog v-model="editVisible" title="编辑用户" width="440px">
      <el-form :model="editForm" label-width="90px">
        <el-form-item label="用户名">
          <el-input :model-value="editForm.username" disabled />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input
            v-model="editForm.password"
            type="password"
            show-password
            placeholder="留空则不修改"
          />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="editForm.role" style="width:100%">
            <el-option label="咨询用户" value="consultant" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="editForm.is_active" active-text="启用" inactive-text="禁用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'
import { formatDate } from '@/utils/format'
import { unwrapPage } from '@/utils/page'

const users = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const creating = ref(false)
const saving = ref(false)
const editVisible = ref(false)
const form = reactive({
  username: '',
  password: '',
  role: 'consultant',
})
const editForm = reactive({
  id: '',
  username: '',
  password: '',
  role: 'consultant',
  is_active: true,
})

onMounted(load)

async function load() {
  loading.value = true
  try {
    const res = await api.getUsers({ page: page.value, page_size: pageSize.value })
    const { items, total: t } = unwrapPage(res)
    users.value = items
    total.value = t
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

async function create() {
  if (!form.username.trim() || form.password.length < 6) {
    ElMessage.warning('请填写用户名和至少 6 位密码')
    return
  }
  creating.value = true
  try {
    await api.createUser({ ...form })
    ElMessage.success('用户已创建')
    form.username = ''
    form.password = ''
    form.role = 'consultant'
    await load()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    creating.value = false
  }
}

function openEdit(row) {
  editForm.id = row.id
  editForm.username = row.username
  editForm.password = ''
  editForm.role = row.role
  editForm.is_active = row.is_active !== false
  editVisible.value = true
}

async function saveEdit() {
  if (editForm.password && editForm.password.length < 6) {
    ElMessage.warning('新密码至少 6 位')
    return
  }
  saving.value = true
  try {
    const payload = {
      role: editForm.role,
      is_active: editForm.is_active,
    }
    if (editForm.password) payload.password = editForm.password
    await api.updateUser(editForm.id, payload)
    ElMessage.success('已保存')
    editVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(`确定删除用户「${row.username}」？`, '确认删除', { type: 'warning' })
    await api.deleteUser(row.id)
    ElMessage.success('已删除')
    await load()
  } catch (e) {
    if (e !== 'cancel' && e?.message) ElMessage.error(e.message)
  }
}
</script>

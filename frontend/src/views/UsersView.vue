<template>
  <div class="center-content">
    <div class="experts-header">
      <h2>用户管理</h2>
      <p>创建咨询账号（登录后仅可访问法律顾问团与咨询对话）</p>
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
            <el-option label="咨询用户（仅法律顾问团）" value="consultant" />
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
      <el-table-column prop="create_date" label="创建时间" width="220" />
    </el-table>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/api'

const users = ref([])
const loading = ref(false)
const creating = ref(false)
const form = reactive({
  username: '',
  password: '',
  role: 'consultant',
})

onMounted(load)

async function load() {
  loading.value = true
  try {
    users.value = await api.getUsers()
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
</script>

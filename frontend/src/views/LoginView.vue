<template>
  <div class="login-page">
    <div class="login-container">
      <div class="login-header">
        <div class="login-logo">⚖</div>
        <h1 class="login-title">AI 智能知识助手</h1>
        <p class="login-subtitle">多行业知识问答平台 · qwen-turbo</p>
      </div>

      <el-form ref="formRef" :model="form" :rules="rules" class="login-form" @submit.prevent="handleLogin">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="请输入用户名" size="large" clearable>
            <template #prefix><el-icon><User /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            size="large"
            show-password
            @keyup.enter="handleLogin"
          >
            <template #prefix><el-icon><Lock /></el-icon></template>
          </el-input>
        </el-form-item>
        <div class="login-options">
          <el-checkbox v-model="form.remember">记住我</el-checkbox>
        </div>
        <button type="button" class="login-btn" :disabled="loading" @click="handleLogin">
          {{ loading ? '登录中...' : '登 录' }}
        </button>
      </el-form>

      <div class="login-footer">
        <p>新环境默认：admin / LegalAi@2026</p>
        <p style="margin-top:4px;">已有数据库可能仍为旧密码 123456</p>
        <p style="margin-top:6px;">© 2024 AI 智能知识助手</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const formRef = ref(null)
const loading = ref(false)

const form = reactive({
  username: localStorage.getItem('login_username') || 'admin',
  password: '',
  remember: true,
})

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名 3-20 个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 30, message: '密码 6-30 个字符', trigger: 'blur' },
  ],
}

async function handleLogin() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    await auth.login(form.username, form.password)
    if (form.remember) {
      localStorage.setItem('login_username', form.username)
    } else {
      localStorage.removeItem('login_username')
    }
    ElMessage.success('登录成功')
    const redirect = auth.isAdmin ? (route.query.redirect || '/experts') : '/experts'
    router.replace(redirect)
  } catch (e) {
    ElMessage.error(e.message || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1e40af 0%, #2563eb 50%, #1d4ed8 100%);
}
.login-container {
  width: 420px;
  background: #fff;
  border-radius: 20px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.25);
  padding: 48px 40px 36px;
  position: relative;
  overflow: hidden;
}
.login-container::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 6px;
  background: linear-gradient(90deg, #2563eb, #93c5fd);
}
.login-header { text-align: center; margin-bottom: 32px; }
.login-logo {
  width: 64px;
  height: 64px;
  border-radius: 16px;
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
  font-size: 32px;
  color: #fff;
  box-shadow: 0 8px 24px rgba(37, 99, 235, 0.35);
}
.login-title { font-size: 26px; font-weight: 700; color: #1e293b; margin-bottom: 8px; }
.login-subtitle { font-size: 14px; color: #94a3b8; }
.login-options { margin: 4px 0 20px; font-size: 13px; }
.login-btn {
  width: 100%;
  height: 48px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 4px 16px rgba(37, 99, 235, 0.35);
  transition: transform 0.2s, box-shadow 0.2s;
}
.login-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(37, 99, 235, 0.45);
}
.login-btn:disabled { opacity: 0.7; cursor: not-allowed; }
.login-footer {
  text-align: center;
  margin-top: 28px;
  padding-top: 20px;
  border-top: 1px solid #f1f5f9;
  font-size: 12px;
  color: #94a3b8;
}
</style>

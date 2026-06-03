<template>
  <div class="ai-container">
    <aside class="ai-sidebar">
      <div class="sidebar-body">
      <template v-if="!isKbDetail">
        <div class="sidebar-header">
          <div class="sidebar-logo">⚖</div>
          <div>
            <div class="sidebar-title">AI 法律顾问</div>
            <div class="sidebar-subtitle">智能法务助手 · qwen-turbo</div>
          </div>
        </div>
        <div class="sidebar-menus">
          <div class="menu-item" :class="{ active: isActive('experts') }" @click="$router.push('/experts')">
            <el-icon><User /></el-icon> 法律顾问团
          </div>
          <template v-if="auth.isAdmin">
            <div class="menu-item" :class="{ active: isActive('kb') }" @click="$router.push('/kb')">
              <el-icon><Collection /></el-icon> 法律知识库
              <span class="kb-badge">{{ store.kbDatasets.length }}</span>
            </div>
            <div class="menu-item" :class="{ active: isActive('chat') }" @click="$router.push('/chat')">
              <el-icon><ChatDotRound /></el-icon> 专家管理
            </div>
            <div class="menu-item" :class="{ active: isActive('users') }" @click="$router.push('/users')">
              <el-icon><Avatar /></el-icon> 用户管理
            </div>
          </template>
        </div>
        <template v-if="auth.isAdmin">
          <div class="sidebar-divider" />
          <div class="sidebar-history">
            <div style="font-size:11px;color:#c0c8d4;padding:0 8px 8px;font-weight:600;">最近咨询</div>
            <div
              v-for="c in store.recentChats"
              :key="c.id"
              class="history-item"
              :class="{ active: route.name === 'chatDetail' && route.params.id === c.id }"
              @click="$router.push(`/chat/${c.id}`)"
            >
              {{ c.name }}
            </div>
            <div v-if="!store.recentChats.length" style="text-align:center;padding:30px 16px;color:#94a3b8;font-size:12px;">
              暂无咨询记录<br />点击下方开始新咨询
            </div>
          </div>
        </template>
        <div v-if="auth.isAdmin" class="sidebar-footer">
          <button class="new-chat-btn" @click="handleNewChat">
            <span>+</span> 新建咨询
          </button>
        </div>
      </template>

      <template v-else>
        <div class="sidebar-header" style="padding-bottom:0;">
          <div style="font-size:12px;color:#64748b;cursor:pointer;" @click="goBackKb">
            <el-icon><ArrowLeft /></el-icon>
            {{ viewingDoc ? '返回文件列表' : '返回知识库' }}
          </div>
          <div style="margin-top:10px;font-size:15px;font-weight:700;color:#0f172a;">
            {{ viewingDoc ? viewingDoc.name : kbName }}
          </div>
        </div>
        <div class="sidebar-menus" style="margin-top:6px;" v-if="!viewingDoc">
          <div class="menu-item" :class="{ active: kbTab === 'dataset' }" @click="setKbTab('dataset')">
            <el-icon><FolderOpened /></el-icon> 文件列表
          </div>
          <div class="menu-item" :class="{ active: kbTab === 'testing' }" @click="setKbTab('testing')">
            <el-icon><Search /></el-icon> 检索测试
          </div>
          <div class="menu-item" :class="{ active: kbTab === 'config' }" @click="setKbTab('config')">
            <el-icon><Setting /></el-icon> 配置
          </div>
        </div>
      </template>
      </div>

      <div v-if="auth.username" class="sidebar-user-bar">
        <span class="sidebar-user-name">
          {{ auth.username }}<span v-if="auth.isConsultant" class="sidebar-user-tag">咨询</span>
        </span>
        <button type="button" class="sidebar-logout-btn" @click="logout">退出</button>
      </div>
    </aside>

    <main class="ai-main-content">
      <router-view v-slot="{ Component }">
        <component :is="Component" />
      </router-view>
    </main>
  </div>
</template>

<script setup>
import { computed, provide, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const store = useAppStore()
const auth = useAuthStore()

const kbTab = ref('dataset')
const viewingDoc = ref(null)
const kbName = ref('')

provide('kbContext', {
  kbTab,
  viewingDoc,
  kbName,
  setKbTab: (t) => { kbTab.value = t },
})

const isKbDetail = computed(() => route.name === 'kbDetail')

function isActive(name) {
  if (name === 'experts') return route.name === 'experts' || (!auth.isAdmin && route.name === 'chatDetail')
  if (name === 'chat') return route.name === 'chat' || route.name === 'chatDetail'
  if (name === 'kb') return route.name === 'kb' || route.name === 'kbDetail'
  return route.name === name
}

function setKbTab(t) {
  kbTab.value = t
  viewingDoc.value = null
}

function goBackKb() {
  if (viewingDoc.value) {
    viewingDoc.value = null
    kbTab.value = 'dataset'
  } else {
    router.push('/kb')
  }
}

function handleNewChat() {
  router.push('/chat')
}

function logout() {
  auth.logout()
  router.replace('/login')
}

watch(
  () => route.name,
  (name) => {
    if (name !== 'kbDetail') {
      viewingDoc.value = null
      kbTab.value = 'dataset'
    }
  }
)
</script>

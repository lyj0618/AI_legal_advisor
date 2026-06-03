<template>
  <div style="display:flex;flex-direction:column;height:100%;">
    <div class="window-header">
      <span class="header-back" @click="goBack">← 返回</span>
      <span class="header-breadcrumb">
        <span class="breadcrumb-item" @click="$router.push('/chat')">助手管理</span>
        <span class="breadcrumb-sep">/</span>
        <span class="breadcrumb-current">{{ chat?.name || '加载中' }}</span>
      </span>
      <span class="header-tabs">
        <span class="htab" :class="{ active: tab === 'dialog' }" @click="tab = 'dialog'">咨询对话</span>
        <span v-if="auth.isAdmin" class="htab" :class="{ active: tab === 'settings' }" @click="tab = 'settings'">设置</span>
      </span>
    </div>

    <div v-show="tab === 'dialog'" class="chat-main" style="flex:1;">
      <div ref="msgBox" class="chat-messages">
        <div v-if="!messages.length && chat?.prompt?.opener" style="text-align:center;padding:40px;color:#94a3b8;font-size:13px;">
          {{ chat.prompt.opener }}
        </div>
        <div v-for="(m, i) in messages" :key="i" :class="'chat-msg ' + (m.role === 'user' ? 'msg-user' : 'msg-assistant')">
          <div class="msg-bubble">
            <template v-if="m.streaming && !m.content">
              <el-icon class="is-loading"><Loading /></el-icon> 正在分析...
            </template>
            <template v-else>{{ m.content }}<span v-if="m.streaming" class="stream-cursor">▌</span></template>
          </div>
        </div>
      </div>
      <div class="chat-input-bar">
        <el-input v-model="input" placeholder="描述您的法律问题..." @keyup.enter="send" />
        <el-button type="primary" :loading="sending" @click="send">发送</el-button>
      </div>
      <p style="font-size:11px;color:#94a3b8;text-align:center;padding:6px;">
        本服务由 qwen-turbo 驱动，回答仅供参考，不构成正式法律意见
      </p>
    </div>

    <div v-show="tab === 'settings' && isTemplate" class="center-content">
      <div class="config-section">
        <h4>发布与展示</h4>
        <el-form label-width="100px" size="small">
          <el-form-item label="发布状态">
            <el-switch v-model="form.is_published" :disabled="!form.kb_ids.length" />
            <span style="margin-left:8px;font-size:12px;color:#94a3b8;">
              {{ form.kb_ids.length ? '发布后咨询用户可在法律顾问团看到' : '需先绑定知识库' }}
            </span>
          </el-form-item>
        </el-form>
      </div>
      <div class="config-section">
        <h4>基本配置</h4>
        <el-form label-width="100px" size="small">
          <el-form-item label="助手名称"><el-input v-model="form.name" /></el-form-item>
          <el-form-item label="专家角色"><el-input v-model="form.expert_role" /></el-form-item>
          <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="2" /></el-form-item>
          <el-form-item label="开场白"><el-input v-model="form.opener" type="textarea" :rows="2" /></el-form-item>
          <el-form-item label="空回复"><el-input v-model="form.empty_response" /></el-form-item>
        </el-form>
      </div>
      <div class="config-section">
        <h4>系统提示词</h4>
        <el-input v-model="form.sys_prompt" type="textarea" :rows="8" placeholder="法律顾问人设与回答规范..." />
      </div>
      <div class="config-section">
        <h4>检索参数</h4>
        <el-form label-width="110px" size="small">
          <el-form-item label="Top-N"><el-input-number v-model="form.top_n" :min="1" :max="20" /></el-form-item>
          <el-form-item label="相似度阈值"><el-input-number v-model="form.similarity_threshold" :min="0.05" :max="0.95" :step="0.05" /></el-form-item>
        </el-form>
      </div>
      <div class="config-section">
        <h4>绑定法律知识库</h4>
        <el-checkbox-group v-model="form.kb_ids">
          <el-checkbox v-for="kb in store.kbDatasets" :key="kb.id" :label="kb.id" style="display:block;margin-bottom:8px;">
            {{ kb.name }}
          </el-checkbox>
        </el-checkbox-group>
      </div>
      <div style="text-align:right;margin-bottom:24px;">
        <el-button @click="loadChat">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api, completionStream } from '@/api'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const store = useAppStore()
const auth = useAuthStore()
const chatId = route.params.id
const tab = ref(route.query.tab === 'settings' ? 'settings' : 'dialog')
const chat = ref(null)
const isTemplate = ref(false)
const messages = ref([])
const input = ref('')
const sending = ref(false)
const saving = ref(false)
const msgBox = ref(null)

const form = reactive({
  name: '',
  description: '',
  expert_role: '',
  opener: '',
  empty_response: '',
  sys_prompt: '',
  top_n: 8,
  similarity_threshold: 0.2,
  kb_ids: [],
  is_published: false,
})

function goBack() {
  router.push(auth.isAdmin ? '/chat' : '/experts')
}

onMounted(async () => {
  if (auth.isAdmin) await store.fetchDatasets()
  await loadChat()
  await loadMessages()
})

watch(
  () => route.query.tab,
  (t) => {
    if (t) tab.value = t
  }
)

async function loadChat() {
  try {
    chat.value = await api.getChat(chatId)
  } catch {
    chat.value = null
  }
  if (!chat.value) {
    ElMessage.error('助手不存在')
    return
  }
  isTemplate.value = !!chat.value.is_template
  if (tab.value === 'settings' && !isTemplate.value) {
    tab.value = 'dialog'
  }
  const p = chat.value.prompt || {}
  form.name = chat.value.name
  form.description = chat.value.description || ''
  form.expert_role = chat.value.expert_role || ''
  form.opener = p.opener || ''
  form.empty_response = p.empty_response || ''
  form.sys_prompt = p.prompt || ''
  form.top_n = p.top_n ?? 8
  form.similarity_threshold = p.similarity_threshold ?? 0.2
  form.kb_ids = (chat.value.datasets || []).map((d) => d.id)
  form.is_published = !!chat.value.is_published
}

async function loadMessages() {
  try {
    messages.value = await api.getMessages(chatId)
  } catch {
    messages.value = []
  }
}

async function send() {
  const q = input.value.trim()
  if (!q || sending.value) return
  messages.value.push({ role: 'user', content: q })
  input.value = ''
  sending.value = true

  const assistantIdx = messages.value.length
  messages.value.push({ role: 'assistant', content: '', streaming: true })
  await scrollBottom()

  try {
    await completionStream(chatId, q, {
      onDelta: (_token, full) => {
        messages.value[assistantIdx].content = full
        scrollBottom()
      },
      onDone: (answer) => {
        messages.value[assistantIdx].content = answer
        messages.value[assistantIdx].streaming = false
        if (auth.isAdmin) store.fetchChats()
      },
    })
  } catch (e) {
    messages.value[assistantIdx] = { role: 'assistant', content: '错误: ' + e.message, streaming: false }
  } finally {
    sending.value = false
    if (messages.value[assistantIdx]) {
      messages.value[assistantIdx].streaming = false
    }
    await scrollBottom()
  }
}

async function scrollBottom() {
  await nextTick()
  if (msgBox.value) msgBox.value.scrollTop = msgBox.value.scrollHeight
}

async function save() {
  saving.value = true
  try {
    await api.updateChat(chatId, {
      name: form.name,
      description: form.description,
      expert_role: form.expert_role,
      kb_ids: form.kb_ids,
      is_published: form.is_published,
      prompt: {
        opener: form.opener,
        empty_response: form.empty_response,
        prompt: form.sys_prompt,
        top_n: form.top_n,
        similarity_threshold: form.similarity_threshold,
      },
    })
    await loadChat()
    await store.fetchChats()
    await store.fetchExperts()
    ElMessage.success('已保存')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.stream-cursor {
  display: inline-block;
  color: #2563eb;
  animation: blink 1s step-end infinite;
  margin-left: 2px;
}
@keyframes blink {
  50% { opacity: 0; }
}
</style>

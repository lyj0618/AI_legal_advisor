<template>
  <div style="display:flex;flex-direction:column;height:100%;">
    <div class="window-header">
      <span class="header-back" @click="goBack">← 返回</span>
      <span class="header-breadcrumb">
        <span class="breadcrumb-item" @click="goBack">{{ isTemplate ? '助手管理' : '助手广场' }}</span>
        <span class="breadcrumb-sep">/</span>
        <span class="breadcrumb-current">{{ chat?.name || '加载中' }}</span>
      </span>
    </div>

    <div v-show="!showSettings" class="chat-main" style="flex:1;">
      <div ref="msgBox" class="chat-messages">
        <div v-if="!messages.length && chat?.prompt?.opener" style="text-align:center;padding:40px;color:#94a3b8;font-size:13px;">
          {{ chat.prompt.opener }}
        </div>
        <div v-for="(m, i) in messages" :key="i" :class="'chat-msg ' + (m.role === 'user' ? 'msg-user' : 'msg-assistant')">
          <div
            v-if="m.role === 'assistant'"
            class="msg-avatar assistant-avatar"
            :style="assistantAvatarStyle"
            :title="chat?.name"
          >
            {{ assistantInitial }}
          </div>
          <div class="msg-content">
            <div class="msg-bubble">
              <div v-if="m.role === 'user' && m.attachments?.length" class="msg-images">
                <AuthImage
                  v-for="(img, j) in m.attachments"
                  :key="j"
                  :url="img.url"
                  :alt="img.name || '图片'"
                />
              </div>
              <template v-if="m.role === 'assistant' && m.streaming && !m.content">
                <el-icon class="is-loading"><Loading /></el-icon> 正在分析...
              </template>
              <template v-else-if="m.role === 'assistant'">
                <AnswerContent :text="m.content" :streaming="m.streaming" />
              </template>
              <template v-else-if="m.content">
                <span class="msg-plain-text">{{ m.content }}</span>
              </template>
            </div>
            <div
              v-if="m.role === 'assistant' && !m.streaming && m.content && m.id"
              class="msg-feedback"
            >
              <button
                type="button"
                class="msg-feedback-btn"
                :class="{ active: m.feedback === 'like' }"
                title="点赞"
                @click="setFeedback(m, 'like')"
              >
                <el-icon><CircleCheck /></el-icon>
                <span>点赞</span>
              </button>
              <button
                type="button"
                class="msg-feedback-btn dislike"
                :class="{ active: m.feedback === 'dislike' }"
                title="差评"
                @click="setFeedback(m, 'dislike')"
              >
                <el-icon><CircleClose /></el-icon>
                <span>差评</span>
              </button>
            </div>
          </div>
          <div v-if="m.role === 'user'" class="msg-avatar user-avatar" :title="auth.username">
            {{ userInitial }}
          </div>
        </div>
      </div>
      <div
        class="chat-input-bar"
        @dragover.prevent
        @drop.prevent="onDropImages"
      >
        <div
          class="chat-input-composer"
          @paste="onPasteImages"
        >
          <div v-if="pendingImages.length" class="chat-inline-images">
            <div v-for="(img, idx) in pendingImages" :key="img.key" class="chat-inline-image-card">
              <div class="chat-inline-image-thumb">
                <img :src="img.preview" :alt="img.name" />
                <button type="button" class="chat-image-remove" @click="removePendingImage(idx)">×</button>
              </div>
              <div class="chat-inline-image-meta">
                <div class="chat-inline-image-name">{{ img.name }}</div>
                <div v-if="img.analyzing" class="chat-inline-image-status analyzing">
                  <el-icon class="is-loading"><Loading /></el-icon> 解析中...
                </div>
                <div v-else-if="img.analysisError" class="chat-inline-image-status error">
                  解析失败：{{ img.analysisError }}
                </div>
                <div v-else-if="img.analysis" class="chat-inline-image-status done">
                  解析完成
                </div>
              </div>
            </div>
          </div>
          <div class="chat-input-field">
            <input
              ref="fileInput"
              type="file"
              accept="image/jpeg,image/png,image/webp,image/gif,image/bmp"
              multiple
              hidden
              @change="onPickImages"
            />
            <el-input
              v-model="input"
              type="textarea"
              :autosize="{ minRows: 2, maxRows: 8 }"
              placeholder="输入问题，或直接粘贴/拖放图片到此处（自动解析内容）..."
              @keydown.enter="onEnterKey"
            />
          </div>
        </div>
        <div class="chat-input-actions">
          <el-button :disabled="sending || pendingImages.length >= maxChatImages" @click="pickImages">
            图片
          </el-button>
          <el-button type="primary" :loading="sending" :disabled="hasAnalyzingImages" @click="send">
            发送
          </el-button>
          <div class="chat-more-menu">
            <button type="button" class="chat-more-trigger" aria-label="更多操作">
              <el-icon><ArrowDown /></el-icon>
            </button>
            <div class="chat-more-popover">
              <button type="button" class="chat-more-item" @click="exportChat">导出</button>
              <button type="button" class="chat-more-item" @click="shareChat">分享</button>
            </div>
          </div>
        </div>
      </div>
      <p style="font-size:11px;color:#94a3b8;text-align:center;padding:6px;">
        支持在输入框粘贴/拖放图片并自动解析；发送后结合知识库生成回答
      </p>
    </div>

    <div v-show="showSettings" class="center-content">
      <div class="config-section">
        <h4>发布与展示</h4>
        <el-form label-width="100px" size="small">
          <el-form-item label="发布状态">
            <el-switch v-model="form.is_published" :disabled="!form.kb_ids.length" />
            <span style="margin-left:8px;font-size:12px;color:#94a3b8;">
              {{ form.kb_ids.length ? '发布后咨询用户可在助手广场看到' : '需先绑定知识库' }}
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
        <el-input v-model="form.sys_prompt" type="textarea" :rows="8" placeholder="助手人设；回答将按「结论/依据/注意事项/兜底回复」版式输出..." />
      </div>
      <div class="config-section">
        <h4>检索参数</h4>
        <el-form label-width="110px" size="small">
          <el-form-item label="Top-N"><el-input-number v-model="form.top_n" :min="1" :max="20" /></el-form-item>
          <el-form-item label="相似度阈值"><el-input-number v-model="form.similarity_threshold" :min="0.05" :max="0.95" :step="0.05" /></el-form-item>
        </el-form>
      </div>
      <div class="config-section">
        <h4>绑定知识库</h4>
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
import { Loading } from '@element-plus/icons-vue'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api, completionStream } from '@/api'
import AnswerContent from '@/components/AnswerContent.vue'
import AuthImage from '@/components/AuthImage.vue'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import { cleanImageAnalysis } from '@/utils/textFormat'

const maxChatImages = 3
const maxChatImageMb = 5

const route = useRoute()
const router = useRouter()
const store = useAppStore()
const auth = useAuthStore()
const chatId = route.params.id
const chat = ref(null)
const isTemplate = ref(false)
const messages = ref([])
const input = ref('')
const sending = ref(false)
const saving = ref(false)
const msgBox = ref(null)
const fileInput = ref(null)
const pendingImages = ref([])

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

const showSettings = computed(
  () => auth.isAdmin && isTemplate.value && route.query.tab === 'settings'
)
const assistantColor = computed(() => chat.value?.color || '#2563eb')
const assistantInitial = computed(() => (chat.value?.name || '助').charAt(0))
const userInitial = computed(() => (auth.username || '用').charAt(0).toUpperCase())
const assistantAvatarStyle = computed(() => ({
  background: `${assistantColor.value}18`,
  color: assistantColor.value,
  border: `1px solid ${assistantColor.value}33`,
}))
const hasAnalyzingImages = computed(() => pendingImages.value.some((img) => img.analyzing))

function goBack() {
  router.push(auth.isAdmin ? '/chat' : '/experts')
}

function onEnterKey(e) {
  if (e.shiftKey) return
  e.preventDefault()
  send()
}

onMounted(async () => {
  if (auth.isAdmin) await store.fetchDatasets()
  await loadChat()
  await loadMessages()
})

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
  if (route.query.tab === 'settings' && !isTemplate.value) {
    router.replace({ name: 'chatDetail', params: { id: chatId }, query: { tab: 'dialog' } })
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
    const list = await api.getMessages(chatId)
    messages.value = list.map((m) => ({
      id: m.id,
      role: m.role,
      content: m.content,
      attachments: m.attachments || [],
      feedback: m.feedback || null,
      streaming: false,
    }))
  } catch {
    messages.value = []
  }
}

function pickImages() {
  fileInput.value?.click()
}

function onPasteImages(e) {
  const items = Array.from(e.clipboardData?.items || [])
  const files = items
    .filter((item) => item.kind === 'file' && item.type.startsWith('image/'))
    .map((item) => item.getAsFile())
    .filter(Boolean)
  if (!files.length) return
  e.preventDefault()
  queueImageFiles(files)
}

function onDropImages(e) {
  const files = Array.from(e.dataTransfer?.files || []).filter((f) => f.type.startsWith('image/'))
  if (!files.length) return
  queueImageFiles(files)
}

function onPickImages(e) {
  const files = Array.from(e.target.files || [])
  e.target.value = ''
  queueImageFiles(files)
}

function appendAnalysisToInput(analysis) {
  const plain = cleanImageAnalysis(analysis)
  if (!plain) return
  input.value = input.value.trim() ? `${input.value.trim()}\n${plain}` : plain
}

async function uploadAndAnalyzeImage(item) {
  const idx = pendingImages.value.findIndex((img) => img.key === item.key)
  if (idx < 0) return
  try {
    const uploaded = await api.uploadChatImage(chatId, item.file, true)
    const current = pendingImages.value[idx]
    if (!current || current.key !== item.key) return
    current.id = uploaded.id
    current.url = uploaded.url
    current.analyzing = false
    if (uploaded.analysis) {
      const plain = cleanImageAnalysis(uploaded.analysis)
      current.analysis = plain
      if (plain) appendAnalysisToInput(plain)
    } else if (uploaded.analysis_error) {
      current.analysisError = uploaded.analysis_error
    }
  } catch (e) {
    const current = pendingImages.value[idx]
    if (current && current.key === item.key) {
      current.analyzing = false
      current.analysisError = e.message || '上传失败'
    }
  }
}

function queueImageFiles(files) {
  if (!files.length) return
  const remain = maxChatImages - pendingImages.value.length
  if (remain <= 0) {
    ElMessage.warning(`最多添加 ${maxChatImages} 张图片`)
    return
  }
  for (const file of files.slice(0, remain)) {
    if (!file.type.startsWith('image/')) {
      ElMessage.warning(`${file.name} 不是图片文件`)
      continue
    }
    if (file.size > maxChatImageMb * 1024 * 1024) {
      ElMessage.warning(`${file.name} 超过 ${maxChatImageMb}MB`)
      continue
    }
    const item = {
      key: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      file,
      id: '',
      url: '',
      name: file.name || '粘贴的图片.png',
      preview: URL.createObjectURL(file),
      analysis: '',
      analysisError: '',
      analyzing: true,
    }
    pendingImages.value.push(item)
    uploadAndAnalyzeImage(item)
  }
}

function removePendingImage(index) {
  const item = pendingImages.value[index]
  if (item?.preview) URL.revokeObjectURL(item.preview)
  pendingImages.value.splice(index, 1)
}

function clearPendingImages() {
  pendingImages.value.forEach((item) => {
    if (item.preview) URL.revokeObjectURL(item.preview)
  })
  pendingImages.value = []
}

onBeforeUnmount(() => {
  clearPendingImages()
})

async function setFeedback(msg, type) {
  if (!msg.id || msg.streaming) return
  const next = msg.feedback === type ? null : type
  try {
    const updated = await api.setMessageFeedback(chatId, msg.id, next)
    msg.feedback = updated.feedback || null
  } catch (e) {
    ElMessage.error(e.message || '评价失败')
  }
}

async function send() {
  const q = input.value.trim()
  if ((!q && !pendingImages.value.length) || sending.value || hasAnalyzingImages.value) return

  const readyImages = pendingImages.value.filter((img) => img.id && !img.analyzing)
  if (pendingImages.value.length && readyImages.length !== pendingImages.value.length) {
    ElMessage.warning('请等待图片解析完成')
    return
  }

  const imageIds = readyImages.map((img) => img.id)
  const attachments = readyImages.map((img) => ({
    id: img.id,
    name: img.name,
    url: img.url,
    analysis: img.analysis || '',
  }))

  messages.value.push({
    role: 'user',
    content: q,
    attachments,
    feedback: null,
    streaming: false,
  })
  input.value = ''
  clearPendingImages()
  sending.value = true

  const assistantIdx = messages.value.length
  messages.value.push({ role: 'assistant', content: '', feedback: null, streaming: true })
  await scrollBottom()

  try {
    await completionStream(
      chatId,
      q,
      {
        onDelta: (_token, full) => {
          messages.value[assistantIdx].content = full
          scrollBottom()
        },
        onDone: (answer, messageId) => {
          messages.value[assistantIdx].content = answer
          messages.value[assistantIdx].streaming = false
          if (messageId) messages.value[assistantIdx].id = messageId
        },
      },
      { imageIds },
    )
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

async function exportChat() {
  try {
    const blob = await api.exportChat(chatId, 'md')
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${chat.value?.name || '咨询记录'}.md`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error(e.message || '导出失败')
  }
}

async function shareChat() {
  try {
    const res = await api.createShareLink(chatId)
    const link = `${window.location.origin}${res.path}`
    await navigator.clipboard.writeText(link)
    ElMessage.success('分享链接已复制（7 天有效）')
  } catch (e) {
    ElMessage.error(e.message || '生成分享链接失败')
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
.chat-more-menu {
  position: relative;
  flex-shrink: 0;
}
.chat-more-trigger {
  width: 36px;
  height: 36px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  color: #64748b;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.chat-more-trigger:hover {
  border-color: #cbd5e1;
  color: #334155;
}
.chat-more-popover {
  position: absolute;
  right: 0;
  bottom: calc(100% + 6px);
  min-width: 88px;
  padding: 4px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.1);
  opacity: 0;
  visibility: hidden;
  transform: translateY(4px);
  transition: opacity 0.15s, visibility 0.15s, transform 0.15s;
  z-index: 10;
}
.chat-more-menu:hover .chat-more-popover {
  opacity: 1;
  visibility: visible;
  transform: translateY(0);
}
.chat-more-item {
  display: block;
  width: 100%;
  padding: 8px 12px;
  border: none;
  background: none;
  text-align: left;
  font-size: 13px;
  color: #334155;
  cursor: pointer;
  border-radius: 6px;
}
.chat-more-item:hover {
  background: #f1f5f9;
}
.msg-content {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  max-width: calc(75% - 46px);
  min-width: 0;
}
.msg-user .msg-content {
  align-items: flex-end;
}
.msg-feedback {
  display: flex;
  gap: 6px;
  margin-top: 6px;
}
.msg-feedback-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  background: #fff;
  color: #64748b;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}
.msg-feedback-btn:hover {
  border-color: #cbd5e1;
  color: #334155;
}
.msg-feedback-btn.active {
  border-color: #2563eb;
  background: #eff6ff;
  color: #2563eb;
}
.msg-feedback-btn.active.dislike {
  border-color: #f87171;
  background: #fef2f2;
  color: #dc2626;
}
.stream-cursor {
  display: inline-block;
  color: #2563eb;
  animation: blink 1s step-end infinite;
  margin-left: 2px;
}
@keyframes blink {
  50% { opacity: 0; }
}
.msg-images {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}
:deep(.chat-msg-image) {
  max-width: 220px;
  max-height: 180px;
  border-radius: 8px;
  object-fit: cover;
  border: 1px solid #e2e8f0;
}
.msg-plain-text {
  white-space: pre-wrap;
  word-break: break-word;
}
.chat-input-composer {
  flex: 1;
  min-width: 0;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #fff;
  padding: 8px 10px;
  transition: border-color 0.15s;
}
.chat-input-composer:focus-within {
  border-color: #93c5fd;
}
.chat-input-composer .chat-input-field :deep(.el-textarea__inner) {
  border: none;
  box-shadow: none;
  padding: 4px 2px;
  resize: none;
}
.chat-inline-images {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 8px;
}
.chat-inline-image-card {
  display: flex;
  gap: 10px;
  padding: 8px;
  border-radius: 10px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}
.chat-inline-image-thumb {
  position: relative;
  flex-shrink: 0;
}
.chat-inline-image-thumb img {
  width: 72px;
  height: 72px;
  object-fit: cover;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}
.chat-inline-image-meta {
  flex: 1;
  min-width: 0;
}
.chat-inline-image-name {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 4px;
}
.chat-inline-image-status {
  font-size: 12px;
  line-height: 1.4;
  margin-top: 4px;
}
.chat-inline-image-status.analyzing {
  color: #64748b;
  display: flex;
  align-items: center;
  gap: 6px;
}
.chat-inline-image-status.done {
  color: #16a34a;
}
.chat-inline-image-status.error {
  color: #dc2626;
}
.chat-image-remove {
  position: absolute;
  top: -6px;
  right: -6px;
  width: 20px;
  height: 20px;
  border: none;
  border-radius: 50%;
  background: #64748b;
  color: #fff;
  cursor: pointer;
  line-height: 1;
  font-size: 14px;
}
.msg-plain-text {
  white-space: pre-wrap;
  word-break: break-word;
}
</style>

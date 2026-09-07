<template>
  <div class="page-wrap">
    <div class="page-header">
      <h2>个性化管理</h2>
      <p class="page-subtitle">自定义对话界面的气泡颜色，设置即时生效。</p>
    </div>

    <div class="config-section">
      <h4>气泡颜色</h4>
      <div class="color-setting-list">
        <div class="color-setting-item">
          <div class="color-setting-label">
            <el-icon><ChatDotRound /></el-icon>
            <span>用户问题气泡</span>
          </div>
          <div class="color-setting-control">
            <el-color-picker v-model="userColor" show-alpha />
            <span class="color-value">{{ userColor }}</span>
          </div>
        </div>

        <div class="color-setting-item">
          <div class="color-setting-label">
            <el-icon><ChatLineRound /></el-icon>
            <span>助手回答气泡</span>
          </div>
          <div class="color-setting-control">
            <el-color-picker v-model="assistantColor" show-alpha />
            <span class="color-value">{{ assistantColor }}</span>
          </div>
        </div>
      </div>

      <div class="color-actions">
        <el-button type="primary" @click="save">保存设置</el-button>
        <el-button @click="reset">恢复默认</el-button>
      </div>
    </div>

    <div class="config-section preview-section">
      <h4>实时预览</h4>
      <div class="bubble-preview">
        <div class="preview-row preview-user">
          <img src="/avatars/default-user-avatar.png" class="preview-avatar" alt="用户头像" />
          <div class="preview-bubble" :style="personalized.userBubbleStyle">
            这是一个用户问题的气泡预览。
          </div>
        </div>
        <div class="preview-row preview-assistant">
          <img src="/avatars/default-assistant-avatar.png" class="preview-avatar" alt="助手头像" />
          <div class="preview-bubble" :style="personalized.assistantBubbleStyle">
            这是一个助手回答的气泡预览。
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { usePersonalizedStore } from '@/stores/personalized'

const personalized = usePersonalizedStore()
const userColor = ref(personalized.userBubbleColor)
const assistantColor = ref(personalized.assistantBubbleColor)

onMounted(() => {
  personalized.restore()
  userColor.value = personalized.userBubbleColor
  assistantColor.value = personalized.assistantBubbleColor
})

function save() {
  personalized.setUserBubbleColor(userColor.value)
  personalized.setAssistantBubbleColor(assistantColor.value)
  ElMessage.success('个性化设置已保存')
}

function reset() {
  personalized.reset()
  userColor.value = personalized.userBubbleColor
  assistantColor.value = personalized.assistantBubbleColor
  ElMessage.success('已恢复默认设置')
}
</script>

<style scoped>
.page-wrap {
  padding: 24px;
  max-width: 800px;
}
.page-header h2 {
  margin: 0 0 6px;
  font-size: 20px;
  font-weight: 700;
}
.page-subtitle {
  margin: 0 0 20px;
  color: #64748b;
  font-size: 13px;
}
.color-setting-list {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.color-setting-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.color-setting-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #334155;
}
.color-setting-control {
  display: flex;
  align-items: center;
  gap: 12px;
}
.color-value {
  font-size: 13px;
  color: #64748b;
  font-family: monospace;
  min-width: 80px;
}
.color-actions {
  margin-top: 24px;
  display: flex;
  gap: 12px;
}
.preview-section {
  margin-top: 18px;
}
.bubble-preview {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
  background: #f8fafc;
  border-radius: 12px;
}
.preview-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}
.preview-user {
  flex-direction: row-reverse;
}
.preview-avatar {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  object-fit: cover;
  flex-shrink: 0;
}
.preview-bubble {
  max-width: 70%;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}
</style>

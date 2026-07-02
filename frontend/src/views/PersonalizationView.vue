<template>
  <div class="center-content">
    <div class="experts-header">
      <h2>个性化管理</h2>
      <p>自定义对话中问题气泡与回答气泡的背景颜色，设置将保存到您的账号并在所有对话中生效。</p>
    </div>

    <el-card shadow="never" style="max-width:640px;">
      <el-form label-width="120px">
        <el-form-item label="问题气泡颜色">
          <div class="color-row">
            <el-color-picker v-model="form.question_bubble_color" color-format="hex" />
            <el-input v-model="form.question_bubble_color" maxlength="7" style="width:120px;" />
          </div>
        </el-form-item>
        <el-form-item label="回答气泡颜色">
          <div class="color-row">
            <el-color-picker v-model="form.answer_bubble_color" color-format="hex" />
            <el-input v-model="form.answer_bubble_color" maxlength="7" style="width:120px;" />
          </div>
        </el-form-item>

        <el-form-item label="效果预览">
          <div class="bubble-preview">
            <div class="preview-msg preview-user">
              <div
                class="preview-bubble"
                :style="{
                  background: form.question_bubble_color,
                  color: bubbleTextColor(form.question_bubble_color),
                }"
              >
                这是一条示例问题
              </div>
            </div>
            <div class="preview-msg preview-assistant">
              <div
                class="preview-bubble"
                :style="{
                  background: form.answer_bubble_color,
                  color: bubbleTextColor(form.answer_bubble_color),
                }"
              >
                这是一条示例回答，展示您选择的颜色效果。
              </div>
            </div>
          </div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="saving" @click="save">保存设置</el-button>
          <el-button @click="resetDefaults">恢复默认</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/api'
import { useAuthStore } from '@/stores/auth'
import {
  DEFAULT_ANSWER_BUBBLE_COLOR,
  DEFAULT_QUESTION_BUBBLE_COLOR,
  bubbleTextColor,
} from '@/utils/bubbleColors'

const auth = useAuthStore()
const saving = ref(false)
const form = reactive({
  question_bubble_color: DEFAULT_QUESTION_BUBBLE_COLOR,
  answer_bubble_color: DEFAULT_ANSWER_BUBBLE_COLOR,
})

function loadFromAuth() {
  form.question_bubble_color = auth.questionBubbleColor
  form.answer_bubble_color = auth.answerBubbleColor
}

async function load() {
  try {
    const data = await api.getPreferences()
    form.question_bubble_color = data.question_bubble_color || DEFAULT_QUESTION_BUBBLE_COLOR
    form.answer_bubble_color = data.answer_bubble_color || DEFAULT_ANSWER_BUBBLE_COLOR
    auth.setBubbleColors(form.question_bubble_color, form.answer_bubble_color)
  } catch {
    loadFromAuth()
  }
}

async function save() {
  saving.value = true
  try {
    const data = await api.updatePreferences({
      question_bubble_color: form.question_bubble_color,
      answer_bubble_color: form.answer_bubble_color,
    })
    auth.setBubbleColors(data.question_bubble_color, data.answer_bubble_color)
    ElMessage.success('个性化设置已保存')
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

function resetDefaults() {
  form.question_bubble_color = DEFAULT_QUESTION_BUBBLE_COLOR
  form.answer_bubble_color = DEFAULT_ANSWER_BUBBLE_COLOR
}

onMounted(load)
</script>

<style scoped>
.color-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.bubble-preview {
  width: 100%;
  max-width: 420px;
  padding: 16px;
  background: #f8fafc;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
}

.preview-msg {
  display: flex;
  margin-bottom: 12px;
}

.preview-msg:last-child {
  margin-bottom: 0;
}

.preview-msg.preview-user {
  justify-content: flex-end;
}

.preview-msg.preview-assistant {
  justify-content: flex-start;
}

.preview-bubble {
  max-width: 85%;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>

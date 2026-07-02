<template>
  <div class="thinking-block">
    <div
      class="thinking-title"
      role="button"
      tabindex="0"
      @click="expanded = !expanded"
      @keydown.enter.prevent="expanded = !expanded"
      @keydown.space.prevent="expanded = !expanded"
    >
      <span class="thinking-title-text">
        <el-icon v-if="streaming" class="is-loading thinking-spinner"><Loading /></el-icon>
        思考过程
      </span>
      <span class="toggle-action">
        <span class="toggle-label">{{ expanded ? '收起' : '展开' }}</span>
        <el-icon class="toggle-icon" :class="{ expanded }"><ArrowDown /></el-icon>
      </span>
    </div>
    <div v-show="expanded" class="thinking-body">
      <pre class="thinking-text">{{ text }}</pre>
      <span v-if="streaming" class="stream-cursor">▌</span>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ArrowDown, Loading } from '@element-plus/icons-vue'

const props = defineProps({
  text: { type: String, default: '' },
  streaming: { type: Boolean, default: false },
})

const expanded = ref(props.streaming)

watch(
  () => props.streaming,
  (val) => {
    if (val) expanded.value = true
  },
)
</script>

<style scoped>
.thinking-block {
  margin-bottom: 10px;
  padding-bottom: 10px;
  border-bottom: 1px dashed #dbe3ef;
}

.thinking-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  cursor: pointer;
  user-select: none;
  color: #64748b;
  font-size: 13px;
  font-weight: 600;
}

.thinking-title:hover {
  color: #2563eb;
}

.thinking-title-text {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.thinking-spinner {
  font-size: 14px;
}

.toggle-action {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-weight: 500;
  flex-shrink: 0;
}

.toggle-icon {
  transition: transform 0.2s ease;
}

.toggle-icon.expanded {
  transform: rotate(180deg);
}

.thinking-body {
  margin-top: 8px;
  max-height: 280px;
  overflow: auto;
  padding: 10px 12px;
  border-radius: 8px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.thinking-text {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.6;
  color: #64748b;
}

.stream-cursor {
  display: inline-block;
  color: #94a3b8;
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  50% { opacity: 0; }
}
</style>

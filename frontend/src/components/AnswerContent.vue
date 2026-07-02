<template>
  <div class="answer-content">
    <template v-if="sections.length && sections[0].title">
      <div v-for="(block, idx) in sections" :key="idx" class="answer-section">
        <div
          v-if="isSourcesSection(block)"
          class="answer-section-title answer-section-title--toggle"
          role="button"
          tabindex="0"
          @click="sourcesExpanded = !sourcesExpanded"
          @keydown.enter.prevent="sourcesExpanded = !sourcesExpanded"
          @keydown.space.prevent="sourcesExpanded = !sourcesExpanded"
        >
          <span>{{ block.title }}</span>
          <span class="toggle-action">
            <span class="toggle-label">{{ sourcesExpanded ? '收起' : '展开' }}</span>
            <el-icon class="toggle-icon" :class="{ expanded: sourcesExpanded }">
              <ArrowDown />
            </el-icon>
          </span>
        </div>
        <div v-else class="answer-section-title">{{ block.title }}</div>
        <div
          v-show="!isSourcesSection(block) || sourcesExpanded"
          class="answer-section-body"
        >
          {{ block.body }}
        </div>
      </div>
    </template>
    <template v-else>
      <span>{{ text }}</span>
    </template>
    <span v-if="streaming" class="stream-cursor">▌</span>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ArrowDown } from '@element-plus/icons-vue'
import { parseAnswerSections } from '@/utils/answerFormat'

const props = defineProps({
  text: { type: String, default: '' },
  streaming: { type: Boolean, default: false },
})

const sections = computed(() => parseAnswerSections(props.text || ''))
const sourcesExpanded = ref(false)

function isSourcesSection(block) {
  return block.title === '回答依据出处'
}
</script>

<style scoped>
.answer-section + .answer-section {
  margin-top: 12px;
}
.answer-section-title {
  font-weight: 700;
  font-size: 15px;
  line-height: 1.5;
  color: #0f172a;
  margin-bottom: 6px;
}
.answer-section-title--toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 0;
  padding: 4px 0;
  cursor: pointer;
  user-select: none;
  border-radius: 6px;
  transition: color 0.15s;
}
.answer-section-title--toggle:hover {
  color: #2563eb;
}
.toggle-action {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-weight: 500;
  font-size: 13px;
  color: #64748b;
  flex-shrink: 0;
}
.answer-section-title--toggle:hover .toggle-action {
  color: #2563eb;
}
.toggle-icon {
  transition: transform 0.2s ease;
}
.toggle-icon.expanded {
  transform: rotate(180deg);
}
.answer-section-body {
  font-size: 14px;
  line-height: 1.65;
  color: #334155;
  white-space: pre-wrap;
  word-break: break-word;
}
.answer-section-title--toggle + .answer-section-body {
  margin-top: 6px;
}
</style>

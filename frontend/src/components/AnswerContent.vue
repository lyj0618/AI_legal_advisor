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
          <AnswerBodyBlocks :body="block.body" />
        </div>
      </div>
    </template>
    <template v-else>
      <AnswerBodyBlocks :body="text" />
    </template>
    <span v-if="streaming" class="stream-cursor">▌</span>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, ref } from 'vue'
import { ArrowDown } from '@element-plus/icons-vue'
import { parseAnswerBodyParts, parseAnswerSections } from '@/utils/answerFormat'

const AnswerBodyBlocks = defineComponent({
  name: 'AnswerBodyBlocks',
  props: {
    body: { type: String, default: '' },
  },
  setup(props) {
    const parts = computed(() => parseAnswerBodyParts(props.body || ''))
    return () => {
      if (!parts.value.length) return null
      return parts.value.map((part, i) => {
        if (part.type === 'list') {
          return h(
            'ul',
            { class: 'answer-bullet-list', key: `list-${i}` },
            part.items.map((item, j) => h('li', { key: j }, item)),
          )
        }
        return h('p', { class: 'answer-para', key: `text-${i}` }, part.text)
      })
    }
  },
})

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
  word-break: break-word;
}
.answer-section-body :deep(.answer-para) {
  margin: 0 0 8px;
  white-space: pre-wrap;
}
.answer-section-body :deep(.answer-para:last-child) {
  margin-bottom: 0;
}
.answer-section-body :deep(.answer-bullet-list) {
  margin: 4px 0 8px;
  padding: 0;
  list-style: none;
}
.answer-section-body :deep(.answer-bullet-list li) {
  position: relative;
  padding-left: 14px;
  margin-bottom: 6px;
  line-height: 1.65;
}
.answer-section-body :deep(.answer-bullet-list li:last-child) {
  margin-bottom: 0;
}
.answer-section-body :deep(.answer-bullet-list li::before) {
  content: '';
  position: absolute;
  left: 0;
  top: 0.58em;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #475569;
}
.answer-section-title--toggle + .answer-section-body {
  margin-top: 6px;
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
</style>

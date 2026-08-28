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
          <template v-if="block.title === '结论' && block.subsections && block.subsections.length">
            <div v-for="(sub, sidx) in block.subsections" :key="sidx" class="answer-subsection">
              <div class="answer-subsection-title">{{ sub.title }}</div>
              <div class="answer-subsection-body">{{ sub.body }}</div>
            </div>
          </template>
          <template v-else>{{ block.body }}</template>
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

const CONCLUSION_SUB_TITLES = ['问题现象', '问题定位', '问题自查', '解决方案', '仍未解决']

function parseConclusionSubsections(body) {
  if (!body) return []
  const lines = body.split('\n')
  const result = []
  let current = null
  for (const line of lines) {
    const trimmed = line.trim()
    const matched = CONCLUSION_SUB_TITLES.find(
      (t) => trimmed === t || trimmed.startsWith(t + '：') || trimmed.startsWith(t + ':'),
    )
    if (matched) {
      if (current && current.body.trim()) result.push(current)
      let rest = ''
      const ci = trimmed.indexOf('：')
      const ei = trimmed.indexOf(':')
      const c = ci >= 0 ? ci : ei
      if (c >= 0 && trimmed.length > c + 1) {
        rest = trimmed.slice(c + 1).trim()
      }
      current = { title: matched, body: rest }
    } else if (current) {
      current.body += (current.body ? '\n' : '') + line
    }
  }
  if (current && current.body.trim()) result.push(current)
  return result
}

const sections = computed(() =>
  parseAnswerSections(props.text || '').map((b) =>
    b.title === '结论' ? { ...b, subsections: parseConclusionSubsections(b.body) } : b,
  ),
)
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
.answer-subsection + .answer-subsection {
  margin-top: 10px;
}
.answer-subsection-title {
  font-weight: 600;
  font-size: 14px;
  line-height: 1.5;
  color: #0f172a;
  margin-bottom: 3px;
}
.answer-subsection-body {
  font-size: 14px;
  line-height: 1.65;
  color: #334155;
  white-space: pre-wrap;
  word-break: break-word;
  padding-left: 2px;
}
</style>

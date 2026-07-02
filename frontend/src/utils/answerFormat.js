/** 助手回答固定版式标题 */
export const ANSWER_SECTION_TITLES = [
  '结论',
  '依据',
  '注意事项',
  '回答依据出处',
  '兜底回复',
]

/**
 * 将助手回答解析为 { title, body } 块；无标题时整段作为正文。
 */
export function parseAnswerSections(text) {
  if (!text) return []

  const titles = ANSWER_SECTION_TITLES
  const lines = text.split('\n')
  let current = null
  const result = []

  for (const line of lines) {
    const trimmed = line.trim()
    if (titles.includes(trimmed)) {
      if (current) {
        current.body = current.body.trim()
        if (current.title || current.body) result.push(current)
      }
      current = { title: trimmed, body: '' }
    } else if (current) {
      current.body += (current.body ? '\n' : '') + line
    } else {
      const prev = result[result.length - 1]
      if (prev && !prev.title) {
        prev.body += (prev.body ? '\n' : '') + line
      } else {
        result.push({ title: '', body: line })
      }
    }
  }
  if (current) {
    current.body = current.body.trim()
    if (current.title || current.body) result.push(current)
  }

  const withTitle = result.filter((b) => b.title)
  if (withTitle.length) {
    const merged = []
    for (const block of withTitle) {
      const body = block.body.trim()
      if (!body && block.title !== '结论' && block.title !== '依据') continue
      const prev = merged[merged.length - 1]
      if (prev && prev.title === block.title) {
        prev.body = `${prev.body}\n\n${body}`.trim()
      } else {
        merged.push({ title: block.title, body })
      }
    }
    return merged.filter((b) => b.body || b.title === '结论' || b.title === '依据')
  }
  const plain = text.trim()
  return plain ? [{ title: '', body: plain }] : []
}

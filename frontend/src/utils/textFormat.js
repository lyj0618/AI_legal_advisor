/** 去除常见 Markdown 符号，保留纯文本 */
export function stripMarkdown(text) {
  if (!text) return text
  let s = text
  s = s.replace(/```[^\n]*\n([\s\S]*?)```/g, '$1')
  s = s.replace(/```([^`]+)```/g, '$1')
  s = s.replace(/^#{1,6}\s+/gm, '')
  s = s.replace(/\*\*([^*]+)\*\*/g, '$1')
  s = s.replace(/__([^_]+)__/g, '$1')
  s = s.replace(/(?<!\*)\*([^*\n]+)\*(?!\*)/g, '$1')
  s = s.replace(/`([^`]+)`/g, '$1')
  s = s.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
  s = s.replace(/^>\s?/gm, '')
  return s.trim()
}

export function cleanImageAnalysis(text) {
  const s = stripMarkdown(text || '')
  if (!s) return ''
  const drop = new Set([
    '图片中的文字内容',
    '文字内容',
    '关键要素',
    '文档类型或主题',
  ])
  const lines = s
    .split('\n')
    .map((line) => line.trim())
    .filter((t) => t && !drop.has(t) && !/^图片中的\S{0,20}$/.test(t))
  return lines.join('\n')
}

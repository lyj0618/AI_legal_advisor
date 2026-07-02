export const DEFAULT_QUESTION_BUBBLE_COLOR = '#2563eb'
export const DEFAULT_ANSWER_BUBBLE_COLOR = '#f1f5f9'

export function bubbleTextColor(hex) {
  const h = (hex || '').replace('#', '')
  if (h.length !== 6) return '#334155'
  const r = parseInt(h.slice(0, 2), 16)
  const g = parseInt(h.slice(2, 4), 16)
  const b = parseInt(h.slice(4, 6), 16)
  const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
  return lum > 0.55 ? '#334155' : '#ffffff'
}

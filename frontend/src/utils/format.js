const DISPLAY_PATTERN = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/

export function formatDate(d) {
  if (!d) return '-'
  const s = String(d).trim()
  if (DISPLAY_PATTERN.test(s)) return s
  try {
    const dt = new Date(d)
    if (Number.isNaN(dt.getTime())) return s
    const pad = (n) => String(n).padStart(2, '0')
    return `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())} ${pad(dt.getHours())}:${pad(dt.getMinutes())}:${pad(dt.getSeconds())}`
  } catch {
    return s
  }
}

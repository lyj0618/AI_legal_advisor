export function formatDate(d) {
  if (!d) return '-'
  try {
    const dt = new Date(d)
    if (Number.isNaN(dt.getTime())) return d
    const pad = (n) => String(n).padStart(2, '0')
    return `${pad(dt.getDate())}/${pad(dt.getMonth() + 1)}/${dt.getFullYear()} ${pad(dt.getHours())}:${pad(dt.getMinutes())}:${pad(dt.getSeconds())}`
  } catch {
    return d
  }
}

const TOKEN_KEY = 'access_token'

/**
 * SSE 流式对话补全
 * @param {string} chatId
 * @param {string} question
 * @param {{
 *   onThinking?: (chunk:string, full:string)=>void,
 *   onDone?: (answer:string, messageId?:number, thinking?:string)=>void,
 *   onError?: (e:Error)=>void
 * }} handlers
 * @param {{ imageIds?: string[] }} options
 */
export async function completionStream(chatId, question, handlers = {}, options = {}) {
  const token = localStorage.getItem(TOKEN_KEY)
  const imageIds = options.imageIds || []
  const res = await fetch(`/api/v1/chats/${chatId}/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ question, stream: true, image_ids: imageIds }),
  })

  if (res.status === 401) {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem('auth_user')
    window.location.href = '/login'
    throw new Error('登录已过期')
  }

  if (!res.ok) {
    const text = await res.text()
    let msg = '请求失败'
    try {
      const j = JSON.parse(text)
      msg = j.message || msg
    } catch {
      msg = text || msg
    }
    throw new Error(msg)
  }

  const contentType = res.headers.get('content-type') || ''
  if (!contentType.includes('text/event-stream')) {
    const j = await res.json()
    if (j.code !== 0) throw new Error(j.message || '请求失败')
    handlers.onDone?.(j.data?.answer || '', j.data?.message_id, j.data?.thinking || '')
    return j.data?.answer || ''
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let answer = ''
  let thinking = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed.startsWith('data:')) continue
      const jsonStr = trimmed.slice(5).trim()
      if (!jsonStr) continue
      try {
        const evt = JSON.parse(jsonStr)
        if (evt.type === 'thinking' && evt.content) {
          thinking += evt.content
          handlers.onThinking?.(evt.content, thinking)
        } else if (evt.type === 'delta' && evt.content) {
          answer += evt.content
        } else if (evt.type === 'done') {
          answer = evt.answer || answer
          thinking = evt.thinking || thinking
          handlers.onDone?.(answer, evt.message_id, thinking)
        } else if (evt.type === 'error') {
          throw new Error(evt.message || '流式输出失败')
        }
      } catch (e) {
        if (e instanceof SyntaxError) continue
        throw e
      }
    }
  }

  return answer
}

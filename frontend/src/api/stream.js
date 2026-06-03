const TOKEN_KEY = 'access_token'

/**
 * SSE 流式对话补全
 * @param {string} chatId
 * @param {string} question
 * @param {{ onDelta?: (t:string)=>void, onDone?: (answer:string)=>void, onError?: (e:Error)=>void }} handlers
 */
export async function completionStream(chatId, question, handlers = {}) {
  const token = localStorage.getItem(TOKEN_KEY)
  const res = await fetch(`/api/v1/chats/${chatId}/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ question, stream: true }),
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
    handlers.onDone?.(j.data?.answer || '')
    return j.data?.answer || ''
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let full = ''

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
        if (evt.type === 'delta' && evt.content) {
          full += evt.content
          handlers.onDelta?.(evt.content, full)
        } else if (evt.type === 'done') {
          full = evt.answer || full
          handlers.onDone?.(full)
        } else if (evt.type === 'error') {
          throw new Error(evt.message || '流式输出失败')
        }
      } catch (e) {
        if (e instanceof SyntaxError) continue
        throw e
      }
    }
  }

  return full
}

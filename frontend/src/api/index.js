import axios from 'axios'

const TOKEN_KEY = 'access_token'

const http = axios.create({
  baseURL: '/api/v1',
  timeout: 120000,
})

http.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

http.interceptors.response.use(
  (res) => {
    const body = res.data
    if (body && typeof body.code === 'number' && body.code !== 0) {
      if (body.code === 401 || body.code === 403) {
        if (body.code === 403) {
          return Promise.reject(new Error(body.message || '无权限'))
        }
        localStorage.removeItem(TOKEN_KEY)
        localStorage.removeItem('auth_user')
        localStorage.removeItem('auth_role')
        if (!window.location.pathname.startsWith('/login')) {
          window.location.href = `/login?redirect=${encodeURIComponent(window.location.pathname)}`
        }
      }
      return Promise.reject(new Error(body.message || '请求失败'))
    }
    const data = body?.data !== undefined ? body.data : res.data
    if (data && typeof data === 'object' && body?.message && body.message !== 'success') {
      data._message = body.message
    }
    return data
  },
  (err) => {
    if (err.response?.status === 403) {
      return Promise.reject(new Error(err.response?.data?.detail || err.response?.data?.message || '无权限'))
    }
    if (err.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem('auth_user')
      localStorage.removeItem('auth_role')
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = `/login?redirect=${encodeURIComponent(window.location.pathname)}`
      }
    }
    const detail = err.response?.data?.detail
    const msg = err.response?.data?.message
      || (Array.isArray(detail)
        ? detail.map((d) => d.msg || d.message).join('; ')
        : detail)
      || (err.response?.status === 404 ? '接口不存在，请重启后端服务' : null)
      || err.message || '网络错误'
    return Promise.reject(new Error(msg))
  }
)

export const api = {
  getHealth: () => http.get('/health'),
  login: (data) => http.post('/auth/login', data),
  getMe: () => http.get('/auth/me'),
  getPreferences: () => http.get('/auth/preferences'),
  updatePreferences: (data) => http.put('/auth/preferences', data),
  logout: () => http.post('/auth/logout'),

  getExperts: (params) => http.get('/experts', { params }),
  consultExpert: (templateId) => http.post(`/experts/${templateId}/consult`),
  getDatasets: (params) => http.get('/datasets', { params }),
  createDataset: (data) => http.post('/datasets', data),
  updateDataset: (id, data) => http.put(`/datasets/${id}`, data),
  deleteDatasets: (ids) => http.delete('/datasets', { data: { ids } }),
  getDocuments: (datasetId, params) => http.get(`/datasets/${datasetId}/documents`, { params }),
  batchProcessDocuments: (datasetId, action) =>
    http.post(`/datasets/${datasetId}/documents/batch-process`, { action }),
  uploadDocument: (datasetId, file) => {
    const fd = new FormData()
    fd.append('file', file)
    return http.post(`/datasets/${datasetId}/documents`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  updateDocument: (datasetId, docId, data) =>
    http.put(`/datasets/${datasetId}/documents/${docId}`, data),
  deleteDocuments: (datasetId, ids) =>
    http.delete(`/datasets/${datasetId}/documents`, { data: { ids } }),
  downloadDocument: async (datasetId, docId, filename = 'download') => {
    const blob = await http.get(`/datasets/${datasetId}/documents/${docId}`, {
      responseType: 'blob',
    })
    if (blob?.type?.includes('application/json')) {
      const text = await blob.text()
      let msg = '下载失败'
      try {
        const json = JSON.parse(text)
        msg = json.message || msg
      } catch {
        /* ignore */
      }
      throw new Error(msg)
    }
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    URL.revokeObjectURL(url)
  },
  getChunks: (datasetId, docId, params) =>
    http.get(`/datasets/${datasetId}/documents/${docId}/chunks`, { params }),
  getCleanedText: (datasetId, docId) =>
    http.get(`/datasets/${datasetId}/documents/${docId}/cleaned-text`),
  updateChunk: (datasetId, docId, chunkId, data) =>
    http.put(`/datasets/${datasetId}/documents/${docId}/chunks/${chunkId}`, data),
  deleteChunks: (datasetId, docId, chunkIds) =>
    http.delete(`/datasets/${datasetId}/documents/${docId}/chunks`, {
      data: { chunk_ids: chunkIds },
    }),
  retrieval: (data) => http.post('/retrieval', data),
  batchRetrieval: (data) => http.post('/retrieval/batch', data),
  rebuildIndex: (datasetId) => http.post(`/datasets/${datasetId}/rebuild-index`),
  getStatsDashboard: () => http.get('/stats/dashboard'),
  exportChat: async (chatId, format = 'md') => {
    const blob = await http.get(`/chats/${chatId}/export`, {
      params: { format },
      responseType: 'blob',
    })
    if (blob instanceof Blob && blob.type?.includes('application/json')) {
      const text = await blob.text()
      let msg = '导出失败'
      try {
        const json = JSON.parse(text)
        msg = json.message || msg
      } catch {
        /* ignore */
      }
      throw new Error(msg)
    }
    return blob
  },
  createShareLink: (chatId) => http.post(`/chats/${chatId}/share`),
  getSharedChat: (token) => http.get(`/share/${token}`),
  getUsers: (params) => http.get('/users', { params }),
  createUser: (data) => http.post('/users', data),
  updateUser: (id, data) => http.put(`/users/${id}`, data),
  deleteUser: (id) => http.delete(`/users/${id}`),

  getChats: (params) => http.get('/chats', { params }),
  getChat: (id) => http.get(`/chats/${id}`),
  createChat: (data) => http.post('/chats', data),
  updateChat: (id, data) => http.put(`/chats/${id}`, data),
  deleteChats: (ids) => http.delete('/chats', { data: { ids } }),
  getMessages: (chatId) => http.get(`/chats/${chatId}/messages`),
  setMessageFeedback: (chatId, messageId, feedback) =>
    http.post(`/chats/${chatId}/messages/${messageId}/feedback`, { feedback }),
  completion: (chatId, question) =>
    http.post(`/chats/${chatId}/completions`, { question, stream: false }),

  uploadChatImage: (chatId, file, analyze = true) => {
    const fd = new FormData()
    fd.append('file', file)
    return http.post(`/chats/${chatId}/images`, fd, {
      params: { analyze: analyze ? 1 : 0 },
      timeout: 180000,
    })
  },

  getQaRecords: (params) => http.get('/admin/qa-records', { params }),
  syncQaRecords: () => http.post('/admin/qa-records/sync'),
  updateQaRecord: (id, data) => http.put(`/admin/qa-records/${id}`, data),
  deleteQaRecord: (id) => http.delete(`/admin/qa-records/${id}`),
}

export { completionStream } from './stream'
export default http

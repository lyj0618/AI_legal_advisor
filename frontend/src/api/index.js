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
    const msg = err.response?.data?.message || err.message || '网络错误'
    return Promise.reject(new Error(msg))
  }
)

export const api = {
  getHealth: () => http.get('/health'),
  login: (data) => http.post('/auth/login', data),
  getMe: () => http.get('/auth/me'),
  logout: () => http.post('/auth/logout'),

  getExperts: () => http.get('/experts'),
  consultExpert: (templateId) => http.post(`/experts/${templateId}/consult`),
  getDatasets: () => http.get('/datasets'),
  createDataset: (data) => http.post('/datasets', data),
  updateDataset: (id, data) => http.put(`/datasets/${id}`, data),
  deleteDatasets: (ids) => http.delete('/datasets', { data: { ids } }),
  getDocuments: (datasetId) => http.get(`/datasets/${datasetId}/documents`),
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
  downloadDocument: (datasetId, docId) =>
    `/api/v1/datasets/${datasetId}/documents/${docId}`,
  getChunks: (datasetId, docId) =>
    http.get(`/datasets/${datasetId}/documents/${docId}/chunks`),
  getCleanedText: (datasetId, docId) =>
    http.get(`/datasets/${datasetId}/documents/${docId}/cleaned-text`),
  updateChunk: (datasetId, docId, chunkId, data) =>
    http.put(`/datasets/${datasetId}/documents/${docId}/chunks/${chunkId}`, data),
  deleteChunks: (datasetId, docId, chunkIds) =>
    http.delete(`/datasets/${datasetId}/documents/${docId}/chunks`, {
      data: { chunk_ids: chunkIds },
    }),
  retrieval: (data) => http.post('/retrieval', data),
  getUsers: () => http.get('/users'),
  createUser: (data) => http.post('/users', data),

  getChats: () => http.get('/chats'),
  getChat: (id) => http.get(`/chats/${id}`),
  createChat: (data) => http.post('/chats', data),
  updateChat: (id, data) => http.put(`/chats/${id}`, data),
  deleteChats: (ids) => http.delete('/chats', { data: { ids } }),
  getMessages: (chatId) => http.get(`/chats/${chatId}/messages`),
  completion: (chatId, question) =>
    http.post(`/chats/${chatId}/completions`, { question, stream: false }),
}

export { completionStream } from './stream'
export default http

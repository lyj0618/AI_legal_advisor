import { defineStore } from 'pinia'
import { api } from '@/api'
import { unwrapPage } from '@/utils/page'

const RECENT_CONSULT_KEY = 'recent_consultations'
const RECENT_MAX = 8

/** 进行中的请求，避免重复发起导致浏览器取消 */
const inflight = {
  experts: null,
  datasets: null,
  chats: null,
}

function recentStorageKey(username) {
  return `${RECENT_CONSULT_KEY}:${username || 'anonymous'}`
}

function runOnce(key, task) {
  if (inflight[key]) return inflight[key]
  inflight[key] = Promise.resolve()
    .then(task)
    .finally(() => {
      inflight[key] = null
    })
  return inflight[key]
}

export const useAppStore = defineStore('app', {
  state: () => ({
    experts: [],
    kbDatasets: [],
    chatsList: [],
    kbLoading: false,
    chatsLoading: false,
    recentChats: [],
  }),

  actions: {
    fetchExperts() {
      return runOnce('experts', async () => {
        const res = await api.getExperts({ page: 1, page_size: 500 })
        this.experts = unwrapPage(res).items
      })
    },
    fetchDatasets() {
      return runOnce('datasets', async () => {
        this.kbLoading = true
        try {
          const res = await api.getDatasets({ page: 1, page_size: 500 })
          this.kbDatasets = unwrapPage(res).items
        } finally {
          this.kbLoading = false
        }
      })
    },
    fetchChats() {
      return runOnce('chats', async () => {
        this.chatsLoading = true
        try {
          const res = await api.getChats({ page: 1, page_size: 500 })
          const list = unwrapPage(res).items
          this.chatsList = list.map((c) => ({
            ...c,
            kb_ids: (c.datasets || []).map((d) => d.id),
            kbNames: (c.datasets || []).map((d) => d.name).join(', '),
            is_published: !!c.is_published,
          }))
        } finally {
          this.chatsLoading = false
        }
      })
    },
    loadRecentConsultations(username) {
      try {
        const raw = localStorage.getItem(recentStorageKey(username))
        this.recentChats = raw ? JSON.parse(raw) : []
      } catch {
        this.recentChats = []
      }
    },
    addRecentConsultation({ id, name }, username) {
      if (!id) return
      const item = { id, name: name || '咨询对话' }
      const rest = this.recentChats.filter((c) => c.id !== id)
      this.recentChats = [item, ...rest].slice(0, RECENT_MAX)
      localStorage.setItem(recentStorageKey(username), JSON.stringify(this.recentChats))
    },
    async init(isAdmin = true, username = '') {
      this.loadRecentConsultations(username)
      const tasks = [this.fetchExperts()]
      if (isAdmin) {
        tasks.push(this.fetchDatasets(), this.fetchChats())
      }
      await Promise.allSettled(tasks)
    },
  },
})

import { defineStore } from 'pinia'
import { api } from '@/api'

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
    async fetchExperts() {
      this.experts = await api.getExperts()
    },
    async fetchDatasets() {
      this.kbLoading = true
      try {
        this.kbDatasets = await api.getDatasets()
      } finally {
        this.kbLoading = false
      }
    },
    async fetchChats() {
      this.chatsLoading = true
      try {
        const list = await api.getChats()
        this.chatsList = list.map((c) => ({
          ...c,
          kb_ids: (c.datasets || []).map((d) => d.id),
          kbNames: (c.datasets || []).map((d) => d.name).join(', '),
          is_published: !!c.is_published,
        }))
        this.recentChats = this.chatsList.slice(0, 8)
      } finally {
        this.chatsLoading = false
      }
    },
    async init(isAdmin = true) {
      await this.fetchExperts()
      if (isAdmin) {
        await Promise.all([this.fetchDatasets(), this.fetchChats()])
      }
    },
  },
})

import { defineStore } from 'pinia'
import { api } from '@/api'

const TOKEN_KEY = 'access_token'
const USER_KEY = 'auth_user'
const ROLE_KEY = 'auth_role'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY) || '',
    username: localStorage.getItem(USER_KEY) || '',
    role: localStorage.getItem(ROLE_KEY) || '',
  }),

  getters: {
    isLoggedIn: (s) => !!s.token,
    isAdmin: (s) => s.role === 'admin',
    isConsultant: (s) => s.role === 'consultant',
  },

  actions: {
    _persist() {
      localStorage.setItem(TOKEN_KEY, this.token)
      localStorage.setItem(USER_KEY, this.username)
      localStorage.setItem(ROLE_KEY, this.role)
    },

    async login(username, password) {
      const data = await api.login({ username, password })
      this.token = data.access_token
      this.username = data.username
      this.role = data.role || 'consultant'
      this._persist()
    },

    async fetchMe() {
      if (!this.token) return
      try {
        const data = await api.getMe()
        this.username = data.username
        this.role = data.role || 'consultant'
        this._persist()
      } catch {
        this.logout()
      }
    },

    logout() {
      this.token = ''
      this.username = ''
      this.role = ''
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
      localStorage.removeItem(ROLE_KEY)
    },

    restore() {
      this.token = localStorage.getItem(TOKEN_KEY) || ''
      this.username = localStorage.getItem(USER_KEY) || ''
      this.role = localStorage.getItem(ROLE_KEY) || ''
    },
  },
})

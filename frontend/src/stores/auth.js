import { defineStore } from 'pinia'
import { api } from '@/api'
import {
  DEFAULT_ANSWER_BUBBLE_COLOR,
  DEFAULT_QUESTION_BUBBLE_COLOR,
} from '@/utils/bubbleColors'

const TOKEN_KEY = 'access_token'
const USER_KEY = 'auth_user'
const ROLE_KEY = 'auth_role'
const Q_COLOR_KEY = 'question_bubble_color'
const A_COLOR_KEY = 'answer_bubble_color'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY) || '',
    username: localStorage.getItem(USER_KEY) || '',
    role: localStorage.getItem(ROLE_KEY) || '',
    questionBubbleColor: localStorage.getItem(Q_COLOR_KEY) || DEFAULT_QUESTION_BUBBLE_COLOR,
    answerBubbleColor: localStorage.getItem(A_COLOR_KEY) || DEFAULT_ANSWER_BUBBLE_COLOR,
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
      localStorage.setItem(Q_COLOR_KEY, this.questionBubbleColor)
      localStorage.setItem(A_COLOR_KEY, this.answerBubbleColor)
    },

    setBubbleColors(question, answer) {
      this.questionBubbleColor = question || DEFAULT_QUESTION_BUBBLE_COLOR
      this.answerBubbleColor = answer || DEFAULT_ANSWER_BUBBLE_COLOR
      localStorage.setItem(Q_COLOR_KEY, this.questionBubbleColor)
      localStorage.setItem(A_COLOR_KEY, this.answerBubbleColor)
    },

    _applyMeData(data) {
      this.username = data.username
      this.role = data.role || 'consultant'
      if (data.question_bubble_color || data.answer_bubble_color) {
        this.setBubbleColors(data.question_bubble_color, data.answer_bubble_color)
      }
      this._persist()
    },

    async login(username, password) {
      const data = await api.login({ username, password })
      this.token = data.access_token
      this.username = data.username
      this.role = data.role || 'consultant'
      this._persist()
      await this.fetchMe()
    },

    async fetchMe() {
      if (!this.token) return
      try {
        const data = await api.getMe()
        this._applyMeData(data)
      } catch {
        this.logout()
      }
    },

    logout() {
      this.token = ''
      this.username = ''
      this.role = ''
      this.questionBubbleColor = DEFAULT_QUESTION_BUBBLE_COLOR
      this.answerBubbleColor = DEFAULT_ANSWER_BUBBLE_COLOR
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
      localStorage.removeItem(ROLE_KEY)
      localStorage.removeItem(Q_COLOR_KEY)
      localStorage.removeItem(A_COLOR_KEY)
    },

    restore() {
      this.token = localStorage.getItem(TOKEN_KEY) || ''
      this.username = localStorage.getItem(USER_KEY) || ''
      this.role = localStorage.getItem(ROLE_KEY) || ''
      this.questionBubbleColor = localStorage.getItem(Q_COLOR_KEY) || DEFAULT_QUESTION_BUBBLE_COLOR
      this.answerBubbleColor = localStorage.getItem(A_COLOR_KEY) || DEFAULT_ANSWER_BUBBLE_COLOR
    },
  },
})

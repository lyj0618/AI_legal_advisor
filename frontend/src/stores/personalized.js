import { defineStore } from 'pinia'

const STORAGE_KEY = 'ai_personalization'

const DEFAULTS = {
  userBubbleColor: '#2563eb',
  assistantBubbleColor: '#f1f5f9',
}

function readStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { ...DEFAULTS }
    const parsed = JSON.parse(raw)
    return {
      userBubbleColor: parsed.userBubbleColor || DEFAULTS.userBubbleColor,
      assistantBubbleColor: parsed.assistantBubbleColor || DEFAULTS.assistantBubbleColor,
    }
  } catch {
    return { ...DEFAULTS }
  }
}

export const usePersonalizedStore = defineStore('personalized', {
  state: () => readStorage(),

  getters: {
    userBubbleStyle: (s) => ({
      backgroundColor: s.userBubbleColor,
      color: isLightColor(s.userBubbleColor) ? '#1f2937' : '#ffffff',
    }),
    assistantBubbleStyle: (s) => ({
      backgroundColor: s.assistantBubbleColor,
      color: isLightColor(s.assistantBubbleColor) ? '#1f2937' : '#ffffff',
    }),
  },

  actions: {
    setUserBubbleColor(color) {
      this.userBubbleColor = color || DEFAULTS.userBubbleColor
      this._persist()
      this._applyToDocument()
    },
    setAssistantBubbleColor(color) {
      this.assistantBubbleColor = color || DEFAULTS.assistantBubbleColor
      this._persist()
      this._applyToDocument()
    },
    reset() {
      this.userBubbleColor = DEFAULTS.userBubbleColor
      this.assistantBubbleColor = DEFAULTS.assistantBubbleColor
      this._persist()
      this._applyToDocument()
    },
    restore() {
      const data = readStorage()
      this.userBubbleColor = data.userBubbleColor
      this.assistantBubbleColor = data.assistantBubbleColor
      this._applyToDocument()
    },
    _persist() {
      try {
        localStorage.setItem(
          STORAGE_KEY,
          JSON.stringify({
            userBubbleColor: this.userBubbleColor,
            assistantBubbleColor: this.assistantBubbleColor,
          })
        )
      } catch {
        // ignore
      }
    },
    _applyToDocument() {
      if (typeof document === 'undefined') return
      document.documentElement.style.setProperty('--user-bubble-bg', this.userBubbleColor)
      document.documentElement.style.setProperty('--assistant-bubble-bg', this.assistantBubbleColor)
      document.documentElement.style.setProperty(
        '--user-bubble-text',
        isLightColor(this.userBubbleColor) ? '#1f2937' : '#ffffff'
      )
      document.documentElement.style.setProperty(
        '--assistant-bubble-text',
        isLightColor(this.assistantBubbleColor) ? '#1f2937' : '#ffffff'
      )
    },
  },
})

function isLightColor(color) {
  if (!color) return false
  const str = String(color).trim()
  let r, g, b
  if (str.startsWith('#')) {
    const hex = str.replace('#', '')
    if (hex.length === 3) {
      r = parseInt(hex[0] + hex[0], 16)
      g = parseInt(hex[1] + hex[1], 16)
      b = parseInt(hex[2] + hex[2], 16)
    } else if (hex.length === 6) {
      r = parseInt(hex.substring(0, 2), 16)
      g = parseInt(hex.substring(2, 4), 16)
      b = parseInt(hex.substring(4, 6), 16)
    } else {
      return false
    }
  } else {
    const m = str.match(/rgba?\(\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)/i)
    if (!m) return false
    r = parseInt(m[1], 10)
    g = parseInt(m[2], 10)
    b = parseInt(m[3], 10)
  }
  if ([r, g, b].some((v) => Number.isNaN(v))) return false
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
  return luminance > 0.6
}

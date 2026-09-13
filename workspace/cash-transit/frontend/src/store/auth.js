import { defineStore } from 'pinia'
import api from '../api/http'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('access') || '',
    user: JSON.parse(localStorage.getItem('user') || 'null'),
  }),
  getters: {
    isLoggedIn: (s) => !!s.token,
    roleText: (s) => s.user?.role_display || '',
  },
  actions: {
    async login(username, password) {
      const data = await api.post('/api/auth/login/', { username, password })
      this.token = data.access
      this.user = data.user
      localStorage.setItem('access', data.access)
      localStorage.setItem('refresh', data.refresh)
      localStorage.setItem('user', JSON.stringify(data.user))
    },
    async refreshMe() {
      this.user = await api.get('/api/auth/me/')
      localStorage.setItem('user', JSON.stringify(this.user))
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('access')
      localStorage.removeItem('refresh')
      localStorage.removeItem('user')
    },
  },
})

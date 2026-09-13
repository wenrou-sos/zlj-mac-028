import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({ baseURL: '/' })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (resp) => resp.data,
  (error) => {
    if (error.response?.status === 401 && !error.config.url.includes('/auth/login')) {
      localStorage.removeItem('access')
      localStorage.removeItem('refresh')
      if (location.hash !== '#/login') location.hash = '#/login'
    }
    const data = error.response?.data
    let msg = '请求失败'
    if (data) {
      msg = data.detail || Object.entries(data)
        .map(([k, v]) => Array.isArray(v) ? v.join('；') : String(v))
        .join('；')
    }
    ElMessage.error(msg)
    return Promise.reject(error)
  },
)

export default api

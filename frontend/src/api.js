import axios from 'axios'

const api = axios.create({
  baseURL: '/push/api',
  timeout: 30000,
})

export default api

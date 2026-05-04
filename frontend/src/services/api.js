import axios from 'axios'

const api = axios.create({
  baseURL: '', // empty - proxy handles routing in dev
})

export const getHealth = () => api.get('/api/health/')

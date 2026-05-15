import axios from 'axios'

const api = axios.create({
  baseURL: '', // empty - proxy handles routing in dev
})

/**
 * Checks the backend health status.
 * @returns {Promise<import('axios').AxiosResponse<{status: string}>>} Resolves with the health response
 */
export const getHealth = () => api.get('/api/health/')

import axios, { AxiosResponse } from 'axios'

const api = axios.create({ baseURL: '' })

/**
 * Checks the backend health status.
 * @returns {Promise<import('axios').AxiosResponse<{status: string}>>} Resolves with the health response
 */
export const getHealth = (): Promise<AxiosResponse<{ status: string }>> =>
  api.get('/api/health/')

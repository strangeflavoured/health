import { vi, describe, it, expect, beforeEach } from 'vitest'

import { getHealth } from './api'

const mockGet = vi.hoisted(() => vi.fn())

vi.mock('axios', () => ({
  default: {
    create: vi.fn(() => ({ get: mockGet })),
  },
}))

describe('getHealth', () => {
  beforeEach(() => {
    mockGet.mockReset()
  })

  it('calls the correct endpoint', async () => {
    mockGet.mockResolvedValue({ data: { status: 'ok' } })
    await getHealth()
    expect(mockGet).toHaveBeenCalledWith('/api/health/')
  })

  it('resolves with the response', async () => {
    mockGet.mockResolvedValue({ data: { status: 'ok' } })
    const result = await getHealth()
    expect(result.data.status).toBe('ok')
  })

  it('propagates errors', async () => {
    mockGet.mockRejectedValue(new Error('network error'))
    await expect(getHealth()).rejects.toThrow('network error')
  })
})

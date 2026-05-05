import { render, screen, waitFor } from '@testing-library/react'
import { vi } from 'vitest'
import App from './App'
import * as api from './services/api'

vi.mock('./services/api')

test('shows ok when backend is healthy', async () => {
  api.getHealth.mockResolvedValue({ data: { status: 'ok' } })
  render(<App />)
  await waitFor(() =>
    expect(screen.getByText(/Backend: ok/)).toBeInTheDocument(),
  )
})

test('shows error when backend is down', async () => {
  api.getHealth.mockRejectedValue(new Error('network'))
  render(<App />)
  await waitFor(() =>
    expect(screen.getByText(/Backend: error/)).toBeInTheDocument(),
  )
})

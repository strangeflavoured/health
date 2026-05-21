import { render, screen, waitFor } from '@testing-library/react'
import { vi } from 'vitest'
import App from './App'
import * as api from './services/api'

vi.mock('./services/api')

test('shows ok when backend is healthy', async () => {
  vi.mocked(api.getHealth).mockResolvedValue({ data: { status: 'ok' } } as any)
  render(<App />)
  await waitFor(() =>
    expect(screen.getByText(/Backend: ok/)).toBeInTheDocument(),
  )
})

test('shows error when backend is down', async () => {
  vi.mocked(api.getHealth).mockRejectedValue(new Error('network') as any)
  render(<App />)
  await waitFor(() =>
    expect(screen.getByText(/Backend: error/)).toBeInTheDocument(),
  )
})

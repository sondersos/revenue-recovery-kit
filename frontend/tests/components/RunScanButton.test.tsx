import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import RunScanButton from '@/components/RunScanButton'

// Mock next/navigation
vi.mock('next/navigation', () => ({
  useRouter: () => ({ refresh: vi.fn() }),
}))

// Mock the API module
vi.mock('@/lib/api', () => ({
  runDetection: vi.fn(),
  generateInsight: vi.fn(),
}))

// Mock sonner so toast calls don't throw in tests
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

import * as api from '@/lib/api'

beforeEach(() => {
  vi.clearAllMocks()
})

describe('RunScanButton', () => {
  it('renders with idle label initially', () => {
    render(<RunScanButton />)
    expect(screen.getByRole('button', { name: 'Run scan' })).toBeInTheDocument()
  })

  it('shows scanning text while runDetection is in flight', async () => {
    // runDetection hangs indefinitely so we can check mid-flight state
    vi.mocked(api.runDetection).mockImplementation(
      () => new Promise(() => {})
    )
    render(<RunScanButton />)
    fireEvent.click(screen.getByRole('button'))
    expect(await screen.findByText('Scanning…')).toBeInTheDocument()
  })

  it('shows generating insight text after scan completes', async () => {
    vi.mocked(api.runDetection).mockResolvedValue({
      detection_run_id: 'abc-123',
      status: 'complete',
      counts: {},
      total_at_risk_usd: 0,
      detection_count: 0,
    })
    vi.mocked(api.generateInsight).mockImplementation(
      () => new Promise(() => {})
    )
    render(<RunScanButton />)
    fireEvent.click(screen.getByRole('button'))
    expect(await screen.findByText('Generating insight…')).toBeInTheDocument()
  })

  it('calls runDetection then generateInsight in order', async () => {
    const mockRun = vi.mocked(api.runDetection)
    const mockInsight = vi.mocked(api.generateInsight)

    mockRun.mockResolvedValue({
      detection_run_id: 'run-999',
      status: 'complete',
      counts: {},
      total_at_risk_usd: 0,
      detection_count: 0,
    })
    mockInsight.mockResolvedValue({
      id: 'ins-1',
      detection_run_id: 'run-999',
      organization_id: 'org-1',
      summary_text: 'ok',
      cost_usd: null,
      generated_at: '2026-01-01T00:00:00Z',
      input_tokens: null,
      output_tokens: null,
      model: 'claude-test',
    })

    render(<RunScanButton />)
    fireEvent.click(screen.getByRole('button'))

    await waitFor(() => {
      expect(mockRun).toHaveBeenCalledOnce()
      expect(mockInsight).toHaveBeenCalledWith('run-999')
    })
  })

  it('calls toast.error when runDetection fails', async () => {
    const { toast } = await import('sonner')
    vi.mocked(api.runDetection).mockRejectedValue(new Error('API unavailable'))
    render(<RunScanButton />)
    fireEvent.click(screen.getByRole('button'))
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('API unavailable')
    })
  })

  it('button returns to idle and is enabled after error', async () => {
    vi.mocked(api.runDetection).mockRejectedValue(new Error('fail'))
    render(<RunScanButton />)
    const btn = screen.getByRole('button')
    fireEvent.click(btn)
    await waitFor(() => {
      expect(btn).not.toBeDisabled()
    })
    expect(btn).toHaveTextContent('Run scan')
  })

  it('button is disabled while scanning', async () => {
    vi.mocked(api.runDetection).mockImplementation(() => new Promise(() => {}))
    render(<RunScanButton />)
    const btn = screen.getByRole('button')
    fireEvent.click(btn)
    await screen.findByText('Scanning…')
    expect(btn).toBeDisabled()
  })
})

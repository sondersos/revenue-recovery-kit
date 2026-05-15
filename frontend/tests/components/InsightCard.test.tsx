import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import InsightCard from '@/components/InsightCard'
import type { Insight } from '@/lib/types'

const MOCK_INSIGHT: Insight = {
  id: '11111111-0000-0000-0000-000000000001',
  detection_run_id: '22222222-0000-0000-0000-000000000002',
  organization_id: '33333333-0000-0000-0000-000000000003',
  summary_text:
    'Your portfolio has $12,000 at risk.\n\nThree stalled invoices require attention.\n\nCall the top two clients today.',
  model: 'claude-sonnet-4-5-20250929',
  cost_usd: 0.0012,
  generated_at: new Date(Date.now() - 2 * 60000).toISOString(),
  input_tokens: 120,
  output_tokens: 80,
}

describe('InsightCard', () => {
  it('renders summary text with whitespace preserved', () => {
    render(<InsightCard insight={MOCK_INSIGHT} />)
    expect(screen.getByText(/Your portfolio has/)).toBeInTheDocument()
  })

  it('renders all three paragraphs', () => {
    render(<InsightCard insight={MOCK_INSIGHT} />)
    const text = screen.getByText(/Your portfolio has \$12,000 at risk/)
    expect(text).toBeInTheDocument()
  })

  it('renders model and token count in footer', () => {
    render(<InsightCard insight={MOCK_INSIGHT} />)
    expect(screen.getByText(/claude-sonnet/)).toBeInTheDocument()
    expect(screen.getByText(/200 tokens/)).toBeInTheDocument()
  })

  it('renders relative timestamp', () => {
    render(<InsightCard insight={MOCK_INSIGHT} />)
    expect(screen.getByText(/ago/)).toBeInTheDocument()
  })

  it('renders empty state when insight is null', () => {
    render(<InsightCard insight={null} />)
    expect(screen.getByText(/No insight yet/)).toBeInTheDocument()
    expect(screen.getByText(/Run scan/)).toBeInTheDocument()
  })

  it('does not render empty state when insight is provided', () => {
    render(<InsightCard insight={MOCK_INSIGHT} />)
    expect(screen.queryByText(/No insight yet/)).not.toBeInTheDocument()
  })
})

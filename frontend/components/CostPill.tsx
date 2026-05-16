import { getCostSummaryServer } from '@/lib/api-server'

export async function CostPill() {
  const summary = await getCostSummaryServer()
  if (!summary || summary.generation_count === 0) return null
  return (
    <span className="text-xs text-gray-400">
      Claude spend: ${summary.total_cost_usd.toFixed(3)} · {summary.generation_count} generation{summary.generation_count !== 1 ? 's' : ''} · avg ${summary.avg_cost_usd.toFixed(3)}
    </span>
  )
}

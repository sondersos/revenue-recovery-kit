import type { Detection, DetectionRun } from '@/lib/types'

function relativeTime(iso: string | null): string {
  if (!iso) return '—'
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

interface Props {
  run: DetectionRun | null
  detections: Detection[]
}

export default function KpiRow({ run, detections }: Props) {
  const totalAtRisk = detections.reduce((sum, d) => sum + (d.amount_usd ?? 0), 0)
  const highCount = detections.filter((d) => d.severity === 'HIGH').length

  const kpis = [
    {
      label: 'Total at risk',
      value: totalAtRisk > 0 ? `$${totalAtRisk.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}` : '$0',
      sub: `${detections.length} detection${detections.length !== 1 ? 's' : ''}`,
      color: totalAtRisk > 0 ? 'text-rose-600' : 'text-gray-400',
    },
    {
      label: 'High severity',
      value: String(highCount),
      sub: 'require immediate action',
      color: highCount > 0 ? 'text-amber-600' : 'text-gray-400',
    },
    {
      label: 'Last scan',
      value: run ? relativeTime(run.started_at) : '—',
      sub: run ? `${run.rule_count} rules, ${run.detection_count} found` : 'No scans yet',
      color: 'text-blue-600',
    },
  ]

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
      {kpis.map((kpi) => (
        <div
          key={kpi.label}
          className="bg-white border border-gray-200 rounded-xl p-5"
        >
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
            {kpi.label}
          </p>
          <p className={`text-3xl font-bold ${kpi.color} mb-1`}>{kpi.value}</p>
          <p className="text-xs text-gray-400">{kpi.sub}</p>
        </div>
      ))}
    </div>
  )
}

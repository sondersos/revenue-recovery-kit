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
      value:
        totalAtRisk > 0
          ? `$${totalAtRisk.toLocaleString('en-US', {
              minimumFractionDigits: 0,
              maximumFractionDigits: 0,
            })}`
          : '$0',
      sub: `${detections.length} detection${detections.length !== 1 ? 's' : ''}`,
      valueColor: totalAtRisk > 0 ? 'text-rose-600' : 'text-gray-300',
      iconPath: 'M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z',
    },
    {
      label: 'High severity',
      value: String(highCount),
      sub: 'require immediate action',
      valueColor: highCount > 0 ? 'text-amber-600' : 'text-gray-300',
      iconPath:
        'M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z',
    },
    {
      label: 'Last scan',
      value: run ? relativeTime(run.started_at) : '—',
      sub: run
        ? `${run.rule_count} rules · ${run.detection_count} found`
        : 'No scans yet',
      valueColor: 'text-forest-700',
      iconPath:
        'M12 6v6l4 2m6-2a10 10 0 11-20 0 10 10 0 0120 0z',
    },
  ]

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
      {kpis.map((kpi) => (
        <div
          key={kpi.label}
          className="bg-white border border-gray-200 rounded-2xl p-6"
        >
          <div className="flex items-center justify-between mb-3">
            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest">
              {kpi.label}
            </p>
            <svg
              className="w-4 h-4 text-gray-200"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.75}
              aria-hidden
            >
              <path strokeLinecap="round" strokeLinejoin="round" d={kpi.iconPath} />
            </svg>
          </div>
          <p className={`text-3xl font-bold mb-1 ${kpi.valueColor}`}>{kpi.value}</p>
          <p className="text-xs text-gray-400">{kpi.sub}</p>
        </div>
      ))}
    </div>
  )
}

import type { Detection } from '@/lib/types'

const SEVERITY_CLASSES: Record<string, string> = {
  HIGH:   'bg-rose-100 text-rose-700',
  MEDIUM: 'bg-amber-100 text-amber-700',
  LOW:    'bg-slate-100 text-slate-600',
}

const SUBJECT_ICON: Record<string, string> = {
  invoice: '🧾',
  contact: '👤',
}

function truncate(s: string, n: number): string {
  return s.length <= n ? s : s.slice(0, n) + '…'
}

interface Props {
  detections: Detection[]
}

export default function TopDetectionsTable({ detections }: Props) {
  if (detections.length === 0) {
    return (
      <div className="bg-white border border-gray-200 rounded-xl p-6">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">
          Top detections
        </h3>
        <p className="text-sm text-gray-400 italic">No detections to display.</p>
      </div>
    )
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-100">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">
          Top detections
        </h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-100">
              <th className="text-left px-4 py-3 font-medium text-gray-500 text-xs">Subject</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500 text-xs">Rule</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500 text-xs">Severity</th>
              <th className="text-right px-4 py-3 font-medium text-gray-500 text-xs">Amount</th>
              <th className="text-right px-4 py-3 font-medium text-gray-500 text-xs">Days</th>
              <th className="text-left px-4 py-3 font-medium text-gray-500 text-xs hidden lg:table-cell">
                Recommended action
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {detections.map((det) => (
              <tr key={det.id} className="hover:bg-gray-50 transition-colors">
                <td className="px-4 py-3 font-mono text-xs text-gray-500">
                  <span title={det.subject_id}>
                    {SUBJECT_ICON[det.subject_type] ?? ''}{' '}
                    {det.subject_id.slice(0, 8)}…
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-700">{det.rule_name}</td>
                <td className="px-4 py-3">
                  <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${SEVERITY_CLASSES[det.severity] ?? ''}`}>
                    {det.severity}
                  </span>
                </td>
                <td className="px-4 py-3 text-right text-gray-700">
                  {det.amount_usd != null
                    ? `$${det.amount_usd.toLocaleString('en-US', { minimumFractionDigits: 2 })}`
                    : '—'}
                </td>
                <td className="px-4 py-3 text-right text-gray-500">
                  {det.days_outstanding ?? '—'}
                </td>
                <td
                  className="px-4 py-3 text-gray-500 hidden lg:table-cell"
                  title={det.recommended_action}
                >
                  {truncate(det.recommended_action, 80)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

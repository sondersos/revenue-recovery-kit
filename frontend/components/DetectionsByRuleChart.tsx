'use client'

import { BarChart } from '@tremor/react'
import type { Detection } from '@/lib/types'

const RULE_LABELS: Record<string, string> = {
  stalled_invoice: 'Stalled invoice',
  stale_lead: 'Stale lead',
  recovery_candidate: 'Recovery candidate',
  sequence_eligible: 'Sequence eligible',
}

interface Props {
  detections: Detection[]
}

export default function DetectionsByRuleChart({ detections }: Props) {
  if (detections.length === 0) {
    return (
      <div className="bg-white border border-gray-200 rounded-xl p-6 mb-6 flex items-center justify-center h-48">
        <p className="text-sm text-gray-400 italic">No detections yet — run a scan to populate this chart.</p>
      </div>
    )
  }

  const ruleCounts: Record<string, { HIGH: number; MEDIUM: number; LOW: number }> = {}
  for (const det of detections) {
    if (!ruleCounts[det.rule_name]) {
      ruleCounts[det.rule_name] = { HIGH: 0, MEDIUM: 0, LOW: 0 }
    }
    ruleCounts[det.rule_name][det.severity]++
  }

  const data = Object.entries(ruleCounts).map(([rule, counts]) => ({
    rule: RULE_LABELS[rule] ?? rule,
    HIGH: counts.HIGH,
    MEDIUM: counts.MEDIUM,
    LOW: counts.LOW,
  }))

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-6 mb-6">
      <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">
        Detections by rule
      </h3>
      <BarChart
        data={data}
        index="rule"
        categories={['HIGH', 'MEDIUM', 'LOW']}
        colors={['rose', 'amber', 'slate']}
        yAxisWidth={32}
        showLegend
        stack={false}
        className="h-52"
      />
    </div>
  )
}

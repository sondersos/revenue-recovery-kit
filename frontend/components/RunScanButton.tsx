'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'
import { runDetection, generateInsight } from '@/lib/api'

type Phase = 'idle' | 'scanning' | 'insight' | 'error'

export default function RunScanButton() {
  const router = useRouter()
  const [phase, setPhase] = useState<Phase>('idle')

  async function handleClick() {
    setPhase('scanning')

    try {
      const run = await runDetection()
      setPhase('insight')
      const insight = await generateInsight(run.detection_run_id)
      setPhase('idle')
      toast.success(`Insight generated · $${insight.cost_usd?.toFixed(3) ?? '0.000'}`)
      router.refresh()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Scan failed')
      setPhase('error')
    }
  }

  const label =
    phase === 'scanning' ? 'Scanning…' :
    phase === 'insight'  ? 'Generating insight…' :
    'Run scan'

  return (
    <div className="flex flex-col items-start gap-2 mb-6">
      <button
        onClick={handleClick}
        disabled={phase === 'scanning' || phase === 'insight'}
        className="inline-flex items-center gap-2 px-5 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-60 disabled:cursor-not-allowed transition-colors shadow-sm"
      >
        {(phase === 'scanning' || phase === 'insight') && (
          <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
        )}
        {label}
      </button>
    </div>
  )
}

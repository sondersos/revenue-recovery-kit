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

  const busy = phase === 'scanning' || phase === 'insight'

  return (
    <button
      onClick={handleClick}
      disabled={busy}
      className="inline-flex items-center gap-2 px-4 py-2 bg-forest-700 text-white rounded-lg text-sm font-medium hover:bg-forest-800 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
    >
      {busy ? (
        <svg className="animate-spin h-3.5 w-3.5 shrink-0" viewBox="0 0 24 24" fill="none" aria-hidden>
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
        </svg>
      ) : (
        <svg className="h-3.5 w-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden>
          <path strokeLinecap="round" strokeLinejoin="round" d="M5.636 5.636a9 9 0 1012.728 0M12 3v9" />
        </svg>
      )}
      {label}
    </button>
  )
}

import type { Insight } from '@/lib/types'

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} minute${mins === 1 ? '' : 's'} ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs} hour${hrs === 1 ? '' : 's'} ago`
  const days = Math.floor(hrs / 24)
  return `${days} day${days === 1 ? '' : 's'} ago`
}

function totalTokens(insight: Insight): number {
  return (insight.input_tokens ?? 0) + (insight.output_tokens ?? 0)
}

interface Props {
  insight: Insight | null
}

export default function InsightCard({ insight }: Props) {
  if (!insight) {
    return (
      <div className="bg-white border border-gray-200 rounded-2xl p-8 mb-6">
        <h2 className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-4">
          Latest Insight
        </h2>
        <div className="flex flex-col items-center justify-center py-8 text-center space-y-2">
          <div className="w-10 h-10 rounded-xl bg-forest-50 flex items-center justify-center mb-2">
            <svg className="w-5 h-5 text-forest-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} aria-hidden>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
            </svg>
          </div>
          <p className="text-sm text-gray-600 font-medium">No insight yet.</p>
          <p className="text-xs text-gray-400">Click &apos;Run scan&apos; to generate your first one.</p>
        </div>
      </div>
    )
  }

  const cost = insight.cost_usd != null ? `$${Number(insight.cost_usd).toFixed(4)}` : ''

  return (
    <div className="relative bg-white border border-gray-200 rounded-2xl p-8 mb-6 overflow-hidden">
      {/* Forest accent bar */}
      <div className="absolute left-0 top-0 bottom-0 w-1 bg-forest-600 rounded-l-2xl" />

      <div className="flex items-center justify-between mb-4">
        <h2 className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest">
          Latest Insight
        </h2>
        <span
          className="text-xs text-gray-400"
          title={new Date(insight.generated_at).toLocaleString()}
        >
          {relativeTime(insight.generated_at)}
        </span>
      </div>
      <p className="text-gray-800 leading-relaxed whitespace-pre-line text-sm">
        {insight.summary_text}
      </p>
      <div className="mt-5 flex items-center gap-3 flex-wrap">
        <span className="inline-flex items-center bg-forest-50 text-forest-700 text-xs font-medium px-2.5 py-1 rounded-full">
          {insight.model}
        </span>
        {cost && (
          <span className="text-xs text-gray-400">{cost}</span>
        )}
        <span className="text-xs text-gray-400">
          {totalTokens(insight).toLocaleString()} tokens
        </span>
      </div>
    </div>
  )
}

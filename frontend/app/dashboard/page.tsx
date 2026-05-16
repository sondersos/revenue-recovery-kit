import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import InsightCard from '@/components/InsightCard'
import KpiRow from '@/components/KpiRow'
import RunScanButton from '@/components/RunScanButton'
import DetectionsByRuleChart from '@/components/DetectionsByRuleChart'
import TopDetectionsTable from '@/components/TopDetectionsTable'
import { CostPill } from '@/components/CostPill'
import LogoutButton from './LogoutButton'
import {
  getLatestInsightServer,
  getLatestDetectionRunServer,
  listDetectionsServer,
} from '@/lib/api-server'

export default async function DashboardPage() {
  const supabase = createClient()
  const {
    data: { user },
  } = await supabase.auth.getUser()
  if (!user) redirect('/login')

  const [insight, latestRun] = await Promise.all([
    getLatestInsightServer(),
    getLatestDetectionRunServer(),
  ])

  const detections = latestRun
    ? await listDetectionsServer(latestRun.id)
    : []

  return (
    <main className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold text-gray-900">Revenue Recovery Kit</h1>
            <p className="text-xs text-gray-400">Automated recovery dashboard</p>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-500 hidden sm:block">{user.email}</span>
            <LogoutButton />
          </div>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Latest Claude insight */}
        <InsightCard insight={insight} />

        {/* KPI metrics */}
        <KpiRow run={latestRun} detections={detections} />

        {/* Run scan */}
        <RunScanButton />

        {/* Chart */}
        <DetectionsByRuleChart detections={detections} />

        {/* Table */}
        <TopDetectionsTable detections={detections} />
      </div>
      <footer className="mt-8 flex justify-end px-4 pb-4">
        <CostPill />
      </footer>
    </main>
  )
}

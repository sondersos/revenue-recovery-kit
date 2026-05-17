import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import InsightCard from '@/components/InsightCard'
import KpiRow from '@/components/KpiRow'
import RunScanButton from '@/components/RunScanButton'
import DetectionsByRuleChart from '@/components/DetectionsByRuleChart'
import TopDetectionsTable from '@/components/TopDetectionsTable'
import { CostPill } from '@/components/CostPill'
import LogoutButton from './LogoutButton'
import Sidebar from '@/components/Sidebar'
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
    <div className="min-h-screen flex bg-gray-50">
      <Sidebar email={user.email ?? ''} />

      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <header className="bg-white border-b border-gray-200 px-8 py-4 flex items-center justify-between shrink-0">
          <div>
            <h1 className="text-sm font-semibold text-gray-900">Dashboard</h1>
            <p className="text-xs text-gray-400">Revenue recovery overview</p>
          </div>
          <div className="flex items-center gap-3">
            <RunScanButton />
            <LogoutButton />
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 px-8 py-8 overflow-auto">
          <div className="mb-8">
            <h2 className="font-serif text-3xl text-gray-900 mb-1">
              Welcome back
            </h2>
            <p className="text-sm text-gray-500">
              Here&apos;s what we found in your latest scan.
            </p>
          </div>

          <KpiRow run={latestRun} detections={detections} />
          <InsightCard insight={insight} />
          <DetectionsByRuleChart detections={detections} />
          <TopDetectionsTable detections={detections} />
        </main>

        <footer className="px-8 py-4 flex justify-end border-t border-gray-100 bg-white">
          <CostPill />
        </footer>
      </div>
    </div>
  )
}

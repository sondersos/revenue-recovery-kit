import { Skeleton } from '@/components/ui/Skeleton'

export default function DashboardLoading() {
  return (
    <div className="p-6 space-y-6">
      {/* KPI row */}
      <div className="grid grid-cols-3 gap-4">
        {[0, 1, 2].map(i => <Skeleton key={i} className="h-24" />)}
      </div>
      {/* Chart */}
      <Skeleton className="h-48" />
      {/* Table */}
      <Skeleton className="h-64" />
      {/* Insight card */}
      <Skeleton className="h-32" />
    </div>
  )
}

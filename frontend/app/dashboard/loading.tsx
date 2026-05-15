export default function DashboardLoading() {
  return (
    <main className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-6xl mx-auto animate-pulse">
        <div className="h-8 bg-gray-200 rounded w-64 mb-8" />
        <div className="h-48 bg-gray-200 rounded-xl mb-6" />
        <div className="grid grid-cols-3 gap-4 mb-6">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-24 bg-gray-200 rounded-xl" />
          ))}
        </div>
        <div className="h-64 bg-gray-200 rounded-xl" />
      </div>
    </main>
  )
}

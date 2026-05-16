'use client'
import { useEffect } from 'react'

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error(error)
  }, [error])

  return (
    <div className="p-8 text-center space-y-3">
      <p className="text-gray-700 font-medium">Dashboard failed to load</p>
      <p className="text-sm text-gray-500">{error.message}</p>
      <button onClick={reset} className="text-sm text-blue-600 underline hover:text-blue-800">
        Retry
      </button>
    </div>
  )
}

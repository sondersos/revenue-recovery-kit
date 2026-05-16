'use client'
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <html>
      <body>
        <div className="min-h-screen flex items-center justify-center p-8">
          <div className="max-w-md w-full text-center space-y-4">
            <h1 className="text-2xl font-semibold text-gray-900">Something went wrong</h1>
            <p className="text-gray-500 text-sm">{error.message}</p>
            <button
              onClick={reset}
              className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm hover:bg-blue-700 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
            >
              Try again
            </button>
          </div>
        </div>
      </body>
    </html>
  )
}

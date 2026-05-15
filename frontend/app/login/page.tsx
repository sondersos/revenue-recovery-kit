import { Suspense } from 'react'
import LoginForm from './LoginForm'

export default function LoginPage() {
  return (
    <main className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="w-full max-w-sm">
        <h1 className="text-2xl font-bold text-center mb-8 text-gray-900">
          Revenue Recovery Kit
        </h1>
        <Suspense>
          <LoginForm />
        </Suspense>
      </div>
    </main>
  )
}

import { Suspense } from 'react'
import LoginForm from './LoginForm'

export default function LoginPage() {
  return (
    <div className="min-h-screen flex">
      {/* Left panel — forest hero */}
      <div className="hidden lg:flex lg:w-[480px] xl:w-[560px] bg-forest-900 flex-col justify-between p-12 relative overflow-hidden shrink-0">
        {/* Subtle dot grid */}
        <div
          className="absolute inset-0 opacity-[0.06]"
          style={{
            backgroundImage:
              'radial-gradient(circle, #fff 1px, transparent 1px)',
            backgroundSize: '28px 28px',
          }}
        />

        <div className="relative z-10">
          <div className="flex items-center gap-2.5 mb-20">
            <div className="w-8 h-8 rounded-lg bg-lime-400 flex items-center justify-center shrink-0">
              <svg className="w-4 h-4 text-forest-950" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
              </svg>
            </div>
            <span className="text-white font-semibold text-sm tracking-tight">
              Revenue Recovery Kit
            </span>
          </div>

          <h1 className="font-serif text-[52px] leading-[1.1] text-white mb-5">
            Recover revenue<br />
            <span className="text-lime-400">automatically.</span>
          </h1>
          <p className="text-forest-200 text-base leading-relaxed max-w-[340px]">
            AI-powered detection of missed invoices, failed payments, and billing gaps — before they become losses.
          </p>
        </div>

        {/* Floating stat cards — Produlis / Slate inspired */}
        <div className="relative z-10 space-y-3">
          <div className="bg-forest-800/70 backdrop-blur-sm border border-forest-700/60 rounded-2xl p-5 max-w-[300px]">
            <p className="text-forest-300 text-[10px] font-semibold uppercase tracking-widest mb-2">
              Revenue at risk detected
            </p>
            <p className="text-white text-3xl font-bold">$124,500</p>
            <p className="text-lime-400 text-xs mt-1.5 font-medium">
              ↑ 18% recovered this quarter
            </p>
          </div>
          <div className="bg-forest-800/70 backdrop-blur-sm border border-forest-700/60 rounded-2xl p-5 max-w-[300px]">
            <p className="text-forest-300 text-[10px] font-semibold uppercase tracking-widest mb-2">
              Avg scan time
            </p>
            <p className="text-white text-3xl font-bold">8ms</p>
            <p className="text-forest-400 text-xs mt-1.5">
              Across 1,000+ contacts
            </p>
          </div>
        </div>
      </div>

      {/* Right panel — login form */}
      <div className="flex-1 flex items-center justify-center bg-white px-8 py-12">
        <div className="w-full max-w-[360px]">
          {/* Mobile logo */}
          <div className="flex items-center gap-2 mb-10 lg:hidden">
            <div className="w-7 h-7 rounded-md bg-forest-700 flex items-center justify-center">
              <span className="text-white font-bold text-xs">R</span>
            </div>
            <span className="font-semibold text-sm text-gray-900">
              Revenue Recovery Kit
            </span>
          </div>

          <h2 className="text-2xl font-semibold text-gray-900 mb-1">
            Welcome back
          </h2>
          <p className="text-sm text-gray-500 mb-8">
            Sign in to your dashboard
          </p>

          <Suspense>
            <LoginForm />
          </Suspense>
        </div>
      </div>
    </div>
  )
}

/**
 * Server-side API client — for use in Server Components and Route Handlers only.
 * Gets the JWT from the server-side Supabase session.
 */
import { createClient } from '@/lib/supabase/server'
import type { Detection, DetectionRun, DetectionRunDetail, Insight } from './types'

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function serverFetch<T>(path: string, options: RequestInit = {}): Promise<T | null> {
  const base = process.env.API_BASE_URL ?? 'http://localhost:8000'

  let token: string | null = null
  try {
    const supabase = createClient()
    const { data } = await supabase.auth.getSession()
    token = data.session?.access_token ?? null
  } catch {
    // No session — return null instead of crashing the page
    return null
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> | undefined),
  }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${base}${path}`, {
    ...options,
    headers,
    cache: 'no-store',
  })

  if (res.status === 204) return null
  if (res.status === 401) return null
  if (!res.ok) return null

  return res.json() as Promise<T>
}

export async function getLatestInsightServer(): Promise<Insight | null> {
  return serverFetch<Insight>('/v1/insights/latest')
}

export async function getLatestDetectionRunServer(): Promise<DetectionRun | null> {
  return serverFetch<DetectionRun>('/v1/detection/runs/latest')
}

export async function getDetectionRunServer(id: string): Promise<DetectionRunDetail | null> {
  return serverFetch<DetectionRunDetail>(`/v1/detection/runs/${id}`)
}

export async function listDetectionsServer(runId: string): Promise<Detection[]> {
  const result = await serverFetch<Detection[]>(`/v1/detection/runs/${runId}/detections`)
  return result ?? []
}

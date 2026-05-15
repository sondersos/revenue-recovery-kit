import { createClient } from '@/lib/supabase/client'
import type {
  Detection,
  DetectionRun,
  DetectionRunDetail,
  Insight,
  RunDetectionResponse,
} from './types'

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public body?: unknown
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

function getApiBase(): string {
  if (typeof window === 'undefined') {
    return process.env.API_BASE_URL ?? 'http://localhost:8000'
  }
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000'
}

async function getToken(): Promise<string | null> {
  if (typeof window === 'undefined') return null
  const supabase = createClient()
  const { data } = await supabase.auth.getSession()
  return data.session?.access_token ?? null
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = await getToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> | undefined),
  }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${getApiBase()}${path}`, { ...options, headers })

  if (res.status === 204) return null as T

  if (!res.ok) {
    let body: unknown
    try { body = await res.json() } catch { body = await res.text() }
    throw new ApiError(res.status, `API error ${res.status}`, body)
  }

  return res.json() as Promise<T>
}

export async function runDetection(windowDays = 30): Promise<RunDetectionResponse> {
  return apiFetch<RunDetectionResponse>('/v1/detection/run', {
    method: 'POST',
    body: JSON.stringify({ window_days: windowDays }),
  })
}

export async function getDetectionRun(id: string): Promise<DetectionRunDetail> {
  return apiFetch<DetectionRunDetail>(`/v1/detection/runs/${id}`)
}

export async function getLatestDetectionRun(): Promise<DetectionRun | null> {
  return apiFetch<DetectionRun | null>('/v1/detection/runs/latest')
}

export async function generateInsight(runId: string): Promise<Insight> {
  return apiFetch<Insight>('/v1/insights', {
    method: 'POST',
    body: JSON.stringify({ detection_run_id: runId }),
  })
}

export async function getLatestInsight(): Promise<Insight | null> {
  return apiFetch<Insight | null>('/v1/insights/latest')
}

export async function listDetections(
  runId: string,
  opts?: { limit?: number }
): Promise<Detection[]> {
  const params = new URLSearchParams()
  if (opts?.limit) params.set('limit', String(opts.limit))
  return apiFetch<Detection[]>(`/v1/detection/runs/${runId}/detections?${params}`)
}

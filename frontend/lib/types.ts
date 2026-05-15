export type Severity = 'LOW' | 'MEDIUM' | 'HIGH'

export interface DetectionRun {
  id: string
  started_at: string
  finished_at: string | null
  status: 'running' | 'complete' | 'failed'
  rule_count: number
  detection_count: number
}

export interface DetectionRunDetail extends DetectionRun {
  detections: Record<string, Detection[]>
}

export interface RunDetectionResponse {
  detection_run_id: string
  status: string
  counts: Record<string, number>
  total_at_risk_usd: number
  detection_count: number
}

export interface Detection {
  id: string
  rule_name: string
  severity: Severity
  subject_type: 'contact' | 'invoice'
  subject_id: string
  amount_usd: number | null
  days_outstanding: number | null
  recommended_action: string
}

export interface Insight {
  id: string
  detection_run_id: string
  organization_id: string
  summary_text: string
  cost_usd: number | null
  generated_at: string
  input_tokens: number | null
  output_tokens: number | null
  model: string
}

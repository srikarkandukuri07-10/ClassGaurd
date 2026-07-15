export interface Student {
  id: number
  name: string
  section: string
  unique_code: string
  connection_status: string
  last_seen: string | null
  monitoring_enabled: boolean
  monitoring_paused: boolean
  pause_reason: string | null
  current_status: string
  warning_count: number
  latest_screenshot?: string | null
  reason?: string
  created_at: string
}

export interface DisableRequest {
  id: number
  student_id: number
  student_name: string
  section: string
  reason: string
  status: string
  created_at: string
  reviewed_at: string | null
}

export interface MonitoringState {
  monitoring_active: boolean
  active_sections: string[]
  total_students: number
  studying_count: number
  off_task_count: number
  suspicious_count: number
  offline_count: number
}

export interface WsEvent {
  event: string
  data: any
}

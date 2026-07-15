const BASE = 'http://localhost:8000'

function getToken(): string | null {
  return localStorage.getItem('token')
}

async function request(path: string, options: RequestInit = {}) {
  const token = getToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${BASE}${path}`, { ...options, headers })
  if (!res.ok) {
    if (res.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/'
    }
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
  }
  return res.json()
}

export const api = {
  login(email: string, password: string) {
    return request('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
  },

  register(email: string, password: string) {
    return request('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
  },

  getState() {
    return request('/api/monitoring/state')
  },

  startMonitoring() {
    return request('/api/monitoring/start', { method: 'POST' })
  },

  stopMonitoring() {
    return request('/api/monitoring/stop', { method: 'POST' })
  },

  getStudents(section?: string) {
    const qs = section ? `?section=${section}` : ''
    return request(`/api/students${qs}`)
  },

  addStudent(name: string, section: string) {
    return request('/api/students/', {
      method: 'POST',
      body: JSON.stringify({ name, section }),
    })
  },

  deleteStudent(id: number) {
    return request(`/api/students/${id}`, { method: 'DELETE' })
  },

  reEnableMonitoring(studentId: number) {
    return request(`/api/students/${studentId}/re-enable`, { method: 'POST' })
  },

  getSections() {
    return request('/api/students/sections')
  },

  getDisableRequests(status?: string) {
    const qs = status ? `?status_filter=${status}` : ''
    return request(`/api/disable-requests${qs}`)
  },

  reviewDisableRequest(requestId: number, action: string) {
    return request('/api/disable-requests/review', {
      method: 'POST',
      body: JSON.stringify({ request_id: requestId, action }),
    })
  },

  getStudentHistory(studentId: number) {
    return request(`/api/students/${studentId}/history`)
  },
}

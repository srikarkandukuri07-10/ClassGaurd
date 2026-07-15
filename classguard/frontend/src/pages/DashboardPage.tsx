import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Shield,
  Play,
  Square,
  LogOut,
  Plus,
  RefreshCw,
  Loader2,
  X,
  Eye,
} from 'lucide-react'
import { Student, MonitoringState } from '../types'
import { api, API_BASE } from '../services/api'
import { wsClient } from '../services/websocket'
import { StatCard } from '../components/StatCard'
import { SectionCard } from '../components/SectionCard'
import { AddStudentModal } from '../components/AddStudentModal'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { DisableRequestsPanel } from '../components/DisableRequestsPanel'

export function DashboardPage() {
  const navigate = useNavigate()
  const [state, setState] = useState<MonitoringState | null>(null)
  const [students, setStudents] = useState<Student[]>([])
  const [loading, setLoading] = useState(true)
  const [openSections, setOpenSections] = useState<Set<string>>(new Set())
  const [showAddModal, setShowAddModal] = useState(false)
  const [confirmAction, setConfirmAction] = useState<{ type: 'start' | 'stop'; handler: () => Promise<void> } | null>(null)
  const [refreshRequests, setRefreshRequests] = useState(0)
  const [toast, setToast] = useState<{ message: string; type: string } | null>(null)
  const [sections, setSections] = useState<string[]>([])
  const [alerts, setAlerts] = useState<any[]>([])
  const [zoomUrl, setZoomUrl] = useState<string | null>(null)
  const [historyStudent, setHistoryStudent] = useState<any | null>(null)
  const [historyLogs, setHistoryLogs] = useState<any[]>([])
  const [loadingHistory, setLoadingHistory] = useState(false)

  const openHistory = async (student: any) => {
    setHistoryStudent(student)
    setLoadingHistory(true)
    setHistoryLogs([])
    try {
      const logs = await api.getStudentHistory(student.id)
      setHistoryLogs(logs)
    } catch (err) {
      console.error(err)
    } finally {
      setLoadingHistory(false)
    }
  }

  const showToast = (message: string, type = 'info') => {
    setToast({ message, type })
    setTimeout(() => setToast(null), 4000)
  }

  const loadData = useCallback(async (silent = false) => {
    try {
      if (!silent) setLoading(true)
      const [st, stu, secData] = await Promise.all([
        api.getState(),
        api.getStudents(),
        api.getSections(),
      ])
      setState(st)
      setStudents(stu)
      const DEFAULT_SECTIONS = ['S01', 'S02', 'S03', 'S04', 'S05']
      const loadedSections = secData.sections || []
      const combined = Array.from(new Set([...DEFAULT_SECTIONS, ...loadedSections])).sort()
      setSections(combined)
      setOpenSections((prev) => {
        if (prev.size === 0 && combined.length > 0) {
          return new Set(combined)
        }
        const next = new Set(prev)
        combined.forEach((sec: string) => {
          if (!prev.has(sec)) {
            next.add(sec)
          }
        })
        return next
      })
    } catch (err: any) {
      console.error('loadData error:', err)
      showToast(err.message || 'Failed to load data', 'warning')
    } finally {
      if (!silent) setLoading(false)
    }
  }, [])

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) {
      navigate('/')
      return
    }

    if (typeof window !== 'undefined' && 'Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission()
    }

    loadData()

    wsClient.connect(token)

    const unsub1 = wsClient.on('student_status', (data) => {
      setStudents((prev) =>
        prev.map((s) =>
          s.id === data.student_id
            ? {
                ...s,
                current_status: data.status,
                warning_count: data.warning_count,
                latest_screenshot: data.screenshot || s.latest_screenshot,
                reason: data.reason || s.reason,
                connection_status: 'connected',
                last_seen: data.last_seen || new Date().toISOString(),
              }
            : s
        )
      )
      api.getState().then(setState).catch(console.error)
    })

    const unsub2 = wsClient.on('disable_requested', (data) => {
      showToast(
        `${data.student_name} (${data.section}) requested monitoring disable`,
        'warning'
      )
      setRefreshRequests((r) => r + 1)
      loadData()
    })

    const unsubNotification = wsClient.on('faculty_notification', (data) => {
      setAlerts((prev) => [
        {
          id: Date.now() + Math.random(),
          student_id: data.student_id,
          student_name: data.student_name,
          section: data.section,
          type: data.type,
          reason: data.reason,
          confidence: data.confidence,
          screenshot: data.screenshot,
          time: data.time,
          warning_count: data.warning_count,
        },
        ...prev
      ].slice(0, 50))
      
      showToast(
        `🚨 ${data.student_name} (${data.section}) Off-Task: ${data.reason}`,
        'warning'
      )

      if (typeof window !== 'undefined' && 'Notification' in window && Notification.permission === 'granted') {
        new Notification(`ClassGuard Alert: ${data.student_name} (${data.section})`, {
          body: `Off-Task: ${data.reason}`,
        })
      }

      api.getState().then(setState).catch(console.error)
    })

    const unsubLiveFrame = wsClient.on('live_frame', (data) => {
      setStudents((prev) =>
        prev.map((s) =>
          s.id === data.student_id
            ? { ...s, latest_screenshot: data.screenshot, reason: data.window_title }
            : s
        )
      )
    })

    const interval = setInterval(() => loadData(true), 30000)

    return () => {
      unsub1()
      unsub2()
      unsubNotification()
      unsubLiveFrame()
      clearInterval(interval)
    }
  }, [navigate, loadData])

  const setMonitoringActive = (active: boolean) => {
    setState((prev) => {
      if (!prev) return { monitoring_active: active, active_sections: [], total_students: 0, studying_count: 0, off_task_count: 0, suspicious_count: 0, offline_count: 0 }
      return { ...prev, monitoring_active: active }
    })
  }

  const handleStart = async () => {
    setMonitoringActive(true)
    try {
      await api.startMonitoring()
      showToast('Monitoring started for all students', 'success')
    } catch (err: any) {
      setMonitoringActive(false)
      showToast(err.message || 'Failed to start monitoring', 'warning')
    }
    loadData()
  }

  const handleStop = async () => {
    setMonitoringActive(false)
    try {
      await api.stopMonitoring()
      showToast('Monitoring stopped', 'info')
    } catch (err: any) {
      setMonitoringActive(true)
      showToast(err.message || 'Failed to stop monitoring', 'warning')
    }
    loadData()
  }

  const requestStart = () => {
    setConfirmAction({ type: 'start', handler: handleStart })
  }

  const requestStop = () => {
    setConfirmAction({ type: 'stop', handler: handleStop })
  }

  const executeConfirmed = async () => {
    if (!confirmAction) return
    const h = confirmAction.handler
    setConfirmAction(null)
    await h()
  }

  const handleAddStudent = async (name: string, section: string) => {
    const result = await api.addStudent(name, section)
    showToast(`${name} added to section ${section}`, 'success')
    loadData()
    return result
  }

  const handleReEnable = async (studentId: number) => {
    await api.reEnableMonitoring(studentId)
    showToast('Monitoring re-enabled', 'success')
    loadData()
  }

  const toggleSection = (sec: string) => {
    setOpenSections((prev) => {
      const next = new Set(prev)
      if (next.has(sec)) next.delete(sec)
      else next.add(sec)
      return next
    })
  }

  const handleLogout = () => {
    localStorage.removeItem('token')
    wsClient.disconnect()
    navigate('/')
  }

  const sectionStudents = (sec: string) =>
    students.filter((s) => s.section === sec)

  return (
    <div className="min-h-screen bg-gray-50">
      {toast && (
        <div
          className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg text-sm font-medium animate-slide-in ${
            toast.type === 'warning'
              ? 'bg-orange-500 text-white'
              : toast.type === 'success'
              ? 'bg-green-500 text-white'
              : 'bg-indigo-600 text-white'
          }`}
        >
          {toast.message}
        </div>
      )}

      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Shield className="w-7 h-7 text-indigo-600" />
            <h1 className="text-xl font-bold text-gray-800">ClassGuard</h1>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowAddModal(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-100 text-indigo-700 rounded-lg hover:bg-indigo-200 text-sm font-medium transition-colors"
            >
              <Plus className="w-4 h-4" /> Add Student
            </button>
            <button
              onClick={() => loadData()}
              className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
              title="Refresh"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
            <button
              onClick={handleLogout}
              className="flex items-center gap-1.5 px-3 py-1.5 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg text-sm transition-colors"
            >
              <LogOut className="w-4 h-4" /> Logout
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {state && (
          <div className="grid grid-cols-5 gap-4">
            <StatCard label="Monitoring" value={state.monitoring_active ? 'ON' : 'OFF'} color={state.monitoring_active ? 'text-green-600' : 'text-gray-400'} />
            <StatCard label="Studying" value={state.studying_count} color="text-green-600" />
            <StatCard label="Off-task" value={state.off_task_count} color="text-red-600" />
            <StatCard label="Suspicious" value={state.suspicious_count} color="text-yellow-600" />
            <StatCard label="Offline" value={state.offline_count} color="text-gray-500" />
          </div>
        )}

        <div className="flex items-center gap-3">
          <button
            onClick={requestStart}
            disabled={state?.monitoring_active}
            className="flex items-center gap-2 px-5 py-2.5 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-colors"
          >
            <Play className="w-4 h-4" /> Start Monitoring
          </button>
          <button
            onClick={requestStop}
            disabled={!state?.monitoring_active}
            className="flex items-center gap-2 px-5 py-2.5 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-colors"
          >
            <Square className="w-4 h-4" /> Stop Monitoring
          </button>
        </div>

        {/* Onboarding & Downloads Section */}
        {(() => {
          const downloadUrl = `${API_BASE}/static/downloads/classguard-setup.exe`
          return (
            <div className="bg-indigo-50/50 border border-indigo-100 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="space-y-1">
                <h3 className="text-sm font-semibold text-indigo-900 flex items-center gap-2">
                  <Eye className="w-4 h-4 text-indigo-600" />
                  Student Onboarding & Download Link
                </h3>
                <p className="text-xs text-indigo-750">
                  Provide this universal link to your students to download the ClassGuard agent on their laptops.
                </p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <input
                  type="text"
                  readOnly
                  value={downloadUrl}
                  className="bg-white border border-indigo-150 px-3 py-1.5 rounded-lg text-xs font-mono text-indigo-800 outline-none w-[280px]"
                />
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(downloadUrl);
                    showToast("Universal installer download link copied to clipboard!", "success");
                  }}
                  className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-sm transition-all"
                >
                  Copy Link
                </button>
              </div>
            </div>
          )
        })()}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
          {/* Left Panel: Requests & Sections */}
          <div className="lg:col-span-2 space-y-6">
            <DisableRequestsPanel refreshTrigger={refreshRequests} />

            <div className="space-y-4">
              <h2 className="text-lg font-semibold text-gray-700">Sections</h2>
              {loading ? (
                <div className="flex items-center justify-center py-12 text-gray-400">
                  <Loader2 className="w-6 h-6 animate-spin mr-2" />
                  Loading...
                </div>
              ) : (
                sections.map((sec) => (
                  <SectionCard
                    key={sec}
                    section={sec}
                    students={sectionStudents(sec)}
                    isOpen={openSections.has(sec)}
                    onToggle={() => toggleSection(sec)}
                    onReEnable={handleReEnable}
                    onViewHistory={openHistory}
                    onViewScreenshot={setZoomUrl}
                  />
                ))
              )}
            </div>
          </div>

          {/* Right Panel: Live AI Alerts */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 space-y-4 max-h-[700px] overflow-y-auto lg:sticky lg:top-6">
            <div className="flex items-center justify-between border-b border-gray-100 pb-3">
              <h2 className="text-sm font-bold text-gray-800 flex items-center gap-2">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
                </span>
                Live AI Observer Feed
              </h2>
              {alerts.length > 0 && (
                <button
                  onClick={() => setAlerts([])}
                  className="text-xs text-gray-400 hover:text-red-500 font-semibold transition-colors"
                >
                  Clear Feed
                </button>
              )}
            </div>

            {alerts.length === 0 ? (
              <div className="py-12 text-center text-gray-400 text-xs italic">
                No off-task alerts. Watching screen shares...
              </div>
            ) : (
              <div className="space-y-2">
                {alerts.map((alert) => (
                  <div
                    key={alert.id}
                    className="p-3 bg-red-50/40 hover:bg-red-50/80 border border-red-100 rounded-xl transition-all flex gap-3 cursor-pointer"
                    onClick={() => {
                      const found = students.find((s) => s.id === alert.student_id);
                      if (found) openHistory(found);
                    }}
                    title="Click to view history timeline"
                  >
                    {alert.screenshot && (
                      <img
                        src={`${API_BASE}${alert.screenshot}`}
                        alt="Alert Screen"
                        className="w-14 h-9 object-cover rounded border border-red-200 shrink-0 self-center"
                      />
                    )}
                    <div className="min-w-0 flex-1 space-y-0.5">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-gray-800 text-xs truncate max-w-[120px]">
                          {alert.student_name}
                        </span>
                        <span className="text-[9px] text-gray-400 shrink-0">
                          {alert.time}
                        </span>
                      </div>
                      <p className="text-[11px] text-red-700 font-medium truncate" title={alert.reason}>
                        {alert.reason}
                      </p>
                      <div className="flex items-center justify-between text-[9px] text-red-500 font-semibold">
                        <span>Confidence: {alert.confidence}%</span>
                        {alert.warning_count && <span>Strike {alert.warning_count}</span>}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </main>

      <AddStudentModal
        open={showAddModal}
        onClose={() => setShowAddModal(false)}
        onAdd={handleAddStudent}
      />

      <ConfirmDialog
        open={confirmAction !== null}
        title={confirmAction?.type === 'start' ? 'Start Monitoring' : 'Stop Monitoring'}
        message={
          confirmAction?.type === 'start'
            ? 'This will enable screen monitoring for all registered students. Continue?'
            : 'This will disable screen monitoring for all students. Any active sessions will end. Continue?'
        }
        confirmLabel={confirmAction?.type === 'start' ? 'Start' : 'Stop'}
        confirmVariant={confirmAction?.type === 'start' ? 'primary' : 'danger'}
        onConfirm={executeConfirmed}
        onCancel={() => setConfirmAction(null)}
      />

      {/* Screen Zoom Modal */}
      {zoomUrl && (
        <div
          className="fixed inset-0 bg-black/90 flex items-center justify-center z-50 p-6 cursor-zoom-out"
          onClick={() => setZoomUrl(null)}
        >
          <div className="relative max-w-5xl max-h-[85vh] overflow-hidden rounded-xl border border-white/10 shadow-2xl">
            <img src={zoomUrl} alt="Screen zoom" className="w-full h-auto object-contain" />
            <button
              className="absolute top-4 right-4 bg-black/60 hover:bg-black/80 text-white rounded-full p-2"
              onClick={() => setZoomUrl(null)}
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Student History Timeline Modal */}
      {historyStudent && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden max-h-[85vh] flex flex-col border border-gray-150">
            <div className="px-6 py-4 bg-gray-50 border-b border-gray-100 flex items-center justify-between shrink-0">
              <div>
                <h2 className="text-base font-bold text-gray-800">Student Monitoring Timeline</h2>
                <p className="text-xs text-gray-400 font-medium mt-0.5">
                  {historyStudent.name} &bull; Section {historyStudent.section}
                </p>
              </div>
              <button
                onClick={() => setHistoryStudent(null)}
                className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 overflow-y-auto flex-1 space-y-6">
              {loadingHistory ? (
                <div className="py-20 text-center text-gray-400 flex flex-col items-center justify-center">
                  <Loader2 className="w-8 h-8 animate-spin text-indigo-600 mb-3" />
                  <span className="font-semibold text-xs">Loading activity logs...</span>
                </div>
              ) : historyLogs.length === 0 ? (
                <div className="py-20 text-center text-gray-400 text-xs italic">
                  No activity history logged.
                </div>
              ) : (
                <div className="relative border-l border-gray-200 ml-4 pl-6 space-y-6">
                  {historyLogs.map((log) => (
                    <div key={log.id} className="relative">
                      {/* Timeline dot */}
                      <span className={`absolute -left-[30px] top-1.5 flex h-3.5 w-3.5 rounded-full border-2 border-white shadow-sm ${
                        log.status === 'off-task' ? 'bg-red-500' : log.status === 'suspicious' ? 'bg-yellow-500' : 'bg-green-500'
                      }`} />
                      
                      <div className="bg-gray-50/40 hover:bg-gray-50 border border-gray-150 rounded-xl p-4 transition-colors flex flex-col sm:flex-row gap-4 justify-between items-start">
                        <div className="space-y-1.5 flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-[10px] text-gray-400 font-semibold">
                              {new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                            </span>
                            <span className={`px-2 py-0.5 rounded text-[9px] font-bold uppercase ${
                              log.status === 'off-task' ? 'bg-red-100 text-red-800' : log.status === 'suspicious' ? 'bg-yellow-100 text-yellow-800' : 'bg-green-100 text-green-800'
                            }`}>
                              {log.status}
                            </span>
                            <span className="text-[10px] text-gray-400 font-medium">
                              Confidence: {Math.round(log.confidence * 100)}%
                            </span>
                          </div>
                          <p className="text-sm font-semibold text-gray-800">
                            {log.reason}
                          </p>
                          <p className="text-xs text-gray-405 truncate font-mono max-w-[400px]" title={log.window_title}>
                            {log.window_title || "N/A"}
                          </p>
                        </div>
                        {log.screenshot && (
                          <div 
                            className="relative w-full sm:w-28 h-16 rounded border border-gray-250 overflow-hidden shadow-sm shrink-0 cursor-zoom-in group self-center"
                            onClick={() => setZoomUrl(`${API_BASE}${log.screenshot}`)}
                          >
                            <img 
                              src={`${API_BASE}${log.screenshot}`} 
                              alt="Timeline screen capture" 
                              className="w-full h-full object-cover transition-transform group-hover:scale-105"
                            />
                            <div className="absolute inset-0 bg-black/10 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                              <Eye className="w-4 h-4 text-white drop-shadow" />
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
            
            <div className="px-6 py-4 border-t border-gray-100 bg-gray-50 flex justify-end shrink-0">
              <button
                onClick={() => setHistoryStudent(null)}
                className="px-4 py-2 border rounded-xl text-gray-600 bg-white hover:bg-gray-50 transition-colors text-xs font-semibold"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

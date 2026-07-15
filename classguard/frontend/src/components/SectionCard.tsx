import { ChevronDown, ChevronUp, Users, Wifi, WifiOff, Copy, Check, MonitorPlay } from 'lucide-react'
import { useState } from 'react'
import { Student } from '../types'
import { API_BASE } from '../services/api'

interface Props {
  section: string
  students: Student[]
  isOpen: boolean
  onToggle: () => void
  onReEnable: (id: number) => void
  onViewHistory: (student: Student) => void
  onViewScreenshot: (url: string) => void
}

const statusColors: Record<string, string> = {
  studying: 'bg-green-100 text-green-800 border border-green-200',
  'off-task': 'bg-red-100 text-red-800 border border-red-200 animate-pulse',
  suspicious: 'bg-yellow-100 text-yellow-800 border border-yellow-200',
  monitoring: 'bg-blue-100 text-blue-800 border border-blue-200',
  disconnected: 'bg-gray-100 text-gray-500 border border-gray-200',
  offline: 'bg-gray-100 text-gray-400 border border-gray-200',
}

function CodeDisplay({ code }: { code: string }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation()
    await navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <span className="inline-flex items-center gap-1 text-[11px] font-mono text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-100">
      {code}
      <button onClick={handleCopy} className="hover:text-indigo-800" title="Copy pairing code">
        {copied ? <Check className="w-3 h-3 text-green-600" /> : <Copy className="w-3 h-3" />}
      </button>
    </span>
  )
}

export function SectionCard({
  section,
  students,
  isOpen,
  onToggle,
  onReEnable,
  onViewHistory,
  onViewScreenshot,
}: Props) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden transition-all duration-200 hover:shadow-md">
      <button
        onClick={onToggle}
        className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
            <Users className="w-5 h-5" />
          </div>
          <h3 className="text-lg font-semibold text-gray-800">Section {section}</h3>
          <span className="text-sm text-gray-400 font-medium">({students.length} registered)</span>
        </div>
        {isOpen ? <ChevronUp className="w-5 h-5 text-gray-400" /> : <ChevronDown className="w-5 h-5 text-gray-400" />}
      </button>

      {isOpen && (
        <div className="border-t border-gray-100 divide-y divide-gray-100">
          {students.length === 0 && (
            <div className="px-6 py-8 text-center text-sm text-gray-400 italic">
              No students registered in this section yet.
            </div>
          )}
          {students.map((s) => (
            <div key={s.id} className="px-6 py-4 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-gray-50/30 transition-colors">
              
              {/* Left Column: Name & Status Info */}
              <div className="flex items-start md:items-center gap-4 flex-1 min-w-0">
                {/* Screenshot Live Thumbnail */}
                <div className="relative group shrink-0">
                  {s.latest_screenshot ? (
                    <div 
                      className="w-16 h-10 rounded border border-gray-200 overflow-hidden shadow-sm cursor-zoom-in relative"
                      onClick={() => onViewScreenshot(`${API_BASE}${s.latest_screenshot}`)}
                      title="Click to zoom screen"
                    >
                      <img
                        src={`${API_BASE}${s.latest_screenshot}`}
                        alt="Desktop Feed"
                        className="w-full h-full object-cover transition-transform duration-200 group-hover:scale-110"
                      />
                      <div className="absolute inset-0 bg-black/10 group-hover:bg-black/0 transition-colors flex items-center justify-center opacity-0 group-hover:opacity-100">
                        <MonitorPlay className="w-4 h-4 text-white drop-shadow" />
                      </div>
                    </div>
                  ) : (
                    <div className="w-16 h-10 bg-gray-50 rounded border border-gray-200 flex flex-col items-center justify-center text-[9px] text-gray-400 italic shrink-0 leading-none">
                      <span>No Feed</span>
                    </div>
                  )}
                </div>

                <div className="space-y-1 min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-gray-800 text-sm truncate max-w-[150px]" title={s.name}>
                      {s.name}
                    </span>
                    <CodeDisplay code={s.unique_code} />
                  </div>
                  
                  {/* Current activity text */}
                  {s.connection_status === 'connected' && s.monitoring_enabled && !s.monitoring_paused ? (
                    <p className="text-[11px] text-gray-500 truncate max-w-[300px]" title={s.latest_screenshot ? `Active: ${s.reason}` : 'Session starting...'}>
                      <span className="font-medium text-gray-600">Active: </span>
                      {s.reason || "System Desktop"}
                    </p>
                  ) : s.monitoring_paused ? (
                    <p className="text-[11px] text-orange-600 truncate max-w-[300px]" title={`Paused: ${s.pause_reason}`}>
                      <span className="font-medium">Paused: </span>
                      "{s.pause_reason || 'Temporary break'}"
                    </p>
                  ) : (
                    <p className="text-[11px] text-gray-400 italic">Monitoring inactive</p>
                  )}
                </div>
              </div>

              {/* Right Column: Connection pill, warnings badge & controls */}
              <div className="flex items-center gap-4 shrink-0 flex-wrap justify-between md:justify-end">
                <div className="flex items-center gap-2">
                  <span
                    className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase tracking-wider ${
                      statusColors[s.current_status] || 'bg-gray-100 text-gray-600'
                    }`}
                  >
                    {s.current_status}
                  </span>

                  <span
                    className={`text-xs px-2 py-0.5 rounded-md font-medium border ${
                      s.warning_count >= 3
                        ? 'bg-red-50 text-red-700 border-red-200'
                        : s.warning_count > 0
                        ? 'bg-yellow-50 text-yellow-700 border-yellow-200'
                        : 'bg-gray-50 text-gray-400 border-gray-100'
                    }`}
                  >
                    {s.warning_count} Warning{s.warning_count !== 1 && 's'}
                  </span>
                </div>

                <div className="flex items-center gap-3">
                  <span
                    className={`flex items-center gap-1 text-xs font-semibold ${
                      s.connection_status === 'connected' ? 'text-green-600' : 'text-gray-400'
                    }`}
                  >
                    {s.connection_status === 'connected' ? (
                      <>
                        <Wifi className="w-3.5 h-3.5" />
                        <span className="hidden sm:inline">Online</span>
                      </>
                    ) : (
                      <>
                        <WifiOff className="w-3.5 h-3.5" />
                        <span className="hidden sm:inline">Offline</span>
                      </>
                    )}
                  </span>

                  <button
                    onClick={() => onViewHistory(s)}
                    className="text-xs px-3 py-1.5 border border-gray-200 rounded-lg text-gray-600 bg-white hover:bg-gray-50 transition-colors font-medium"
                  >
                    Timeline
                  </button>

                  {s.monitoring_paused && (
                    <button
                      onClick={() => onReEnable(s.id)}
                      className="text-xs bg-indigo-600 text-white px-3 py-1.5 rounded-lg hover:bg-indigo-700 transition-colors font-semibold shadow-sm"
                    >
                      Re-enable
                    </button>
                  )}
                </div>
              </div>

            </div>
          ))}
        </div>
      )}
    </div>
  )
}

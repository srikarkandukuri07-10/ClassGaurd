import { useState } from "react";

interface StudentInfo {
  student_name: string;
  section: string;
  device_token: string;
  monitoring_enabled: boolean;
  monitoring_paused: boolean;
}

interface WarningEvent {
  level: number;
  message: string;
  reason: string;
}

interface Props {
  student: StudentInfo;
  monitoringActive: boolean;
  monitoringPaused: boolean;
  warnings: WarningEvent[];
  onDisconnect: () => void;
  onRequestPause: (reason: string) => void;
}

export default function DashboardView({
  student,
  monitoringActive,
  monitoringPaused,
  warnings,
  onDisconnect,
  onRequestPause,
}: Props) {
  const [showPauseModal, setShowPauseModal] = useState(false);
  const [pauseReason, setPauseReason] = useState("");

  const handlePauseSubmit = () => {
    if (!pauseReason.trim()) return;
    onRequestPause(pauseReason.trim());
    setPauseReason("");
    setShowPauseModal(false);
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-sm mx-auto space-y-5">
        <div className="bg-white rounded-2xl shadow-lg p-6 text-center">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
          </div>
          <h2 className="text-xl font-bold text-gray-900">{student.student_name}</h2>
          <p className="text-gray-500">Section {student.section}</p>
          <div className="mt-3 inline-flex items-center gap-1.5 bg-green-50 text-green-700 text-xs font-medium px-3 py-1 rounded-full">
            <span className="w-2 h-2 bg-green-500 rounded-full"></span>
            Connected
          </div>
        </div>

        <div className="bg-white rounded-2xl shadow-lg p-5 space-y-3">
          <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Monitoring</h3>
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-600">Status</span>
            <span className={`text-sm font-medium ${monitoringPaused ? "text-orange-600" : monitoringActive ? "text-green-600" : "text-gray-400"}`}>
              {monitoringPaused ? "Paused" : monitoringActive ? "Active" : "Idle"}
            </span>
          </div>
          {monitoringPaused && (
            <p className="text-xs text-orange-600 bg-orange-50 rounded-lg px-3 py-2">
              Monitoring is paused. Faculty will review your request.
            </p>
          )}
        </div>

        {warnings.length > 0 && (
          <div className="bg-white rounded-2xl shadow-lg p-5 space-y-3">
            <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Warnings</h3>
            <div className="space-y-2 max-h-40 overflow-y-auto">
              {warnings.map((w, i) => (
                <div key={i} className="bg-red-50 border border-red-100 rounded-lg px-3 py-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-red-700">Warning #{w.level}</span>
                    <span className="text-[10px] text-gray-400">{i === 0 ? "Just now" : `${i + 1} ago`}</span>
                  </div>
                  <p className="text-xs text-red-600 mt-0.5">{w.message}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="flex gap-3">
          <button
            onClick={() => setShowPauseModal(true)}
            disabled={monitoringPaused}
            className="flex-1 py-2.5 bg-orange-500 text-white text-sm font-medium rounded-xl hover:bg-orange-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Request Pause
          </button>
          <button
            onClick={onDisconnect}
            className="flex-1 py-2.5 bg-red-500 text-white text-sm font-medium rounded-xl hover:bg-red-600 transition-colors"
          >
            Disconnect
          </button>
        </div>

        <p className="text-center text-[10px] text-gray-400">
          ClassGuard Agent v1.0 &middot; Running in background
        </p>
      </div>

      {showPauseModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-6">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6 space-y-4">
            <h3 className="text-lg font-semibold text-gray-800">Request Pause</h3>
            <p className="text-sm text-gray-500">Why do you need to pause monitoring?</p>
            <textarea
              value={pauseReason}
              onChange={(e) => setPauseReason(e.target.value)}
              placeholder="e.g., I need to look up a reference..."
              className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 outline-none resize-none"
              rows={3}
              autoFocus
            />
            <div className="flex gap-3">
              <button
                onClick={() => setShowPauseModal(false)}
                className="flex-1 py-2.5 border border-gray-200 text-gray-700 text-sm font-medium rounded-xl hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handlePauseSubmit}
                disabled={!pauseReason.trim()}
                className="flex-1 py-2.5 bg-orange-500 text-white text-sm font-medium rounded-xl hover:bg-orange-600 disabled:opacity-50 transition-colors"
              >
                Submit
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

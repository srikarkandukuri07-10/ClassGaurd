import { useEffect, useState } from 'react'
import { Clock, CheckCircle, XCircle } from 'lucide-react'
import { DisableRequest } from '../types'
import { api } from '../services/api'

interface Props {
  refreshTrigger: number
}

export function DisableRequestsPanel({ refreshTrigger }: Props) {
  const [requests, setRequests] = useState<DisableRequest[]>([])

  const load = async () => {
    try {
      const data = await api.getDisableRequests('pending')
      setRequests(data)
    } catch {}
  }

  useEffect(() => {
    load()
  }, [refreshTrigger])

  const handleReview = async (id: number, action: string) => {
    try {
      await api.reviewDisableRequest(id, action)
      load()
    } catch {}
  }

  if (requests.length === 0) return null

  return (
    <div className="bg-white rounded-lg shadow-md p-4">
      <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
        <Clock className="w-4 h-4 text-orange-500" />
        Pending Disable Requests ({requests.length})
      </h3>
      <div className="space-y-2">
        {requests.map((req) => (
          <div
            key={req.id}
            className="flex items-center justify-between p-3 bg-orange-50 rounded-lg border border-orange-200"
          >
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-800">
                {req.student_name} <span className="text-gray-500">({req.section})</span>
              </p>
              <p className="text-xs text-gray-500 mt-0.5">"{req.reason}"</p>
            </div>
            <div className="flex gap-2 ml-3">
              <button
                onClick={() => handleReview(req.id, 'approved')}
                className="p-1.5 bg-green-100 text-green-700 rounded hover:bg-green-200 transition-colors"
                title="Approve"
              >
                <CheckCircle className="w-4 h-4" />
              </button>
              <button
                onClick={() => handleReview(req.id, 'rejected')}
                className="p-1.5 bg-red-100 text-red-700 rounded hover:bg-red-200 transition-colors"
                title="Reject"
              >
                <XCircle className="w-4 h-4" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

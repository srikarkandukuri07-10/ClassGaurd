import { useState } from 'react'
import { X, Copy, Check } from 'lucide-react'

interface Props {
  open: boolean
  onClose: () => void
  onAdd: (name: string, section: string) => Promise<any>
}

export function AddStudentModal({ open, onClose, onAdd }: Props) {
  const [name, setName] = useState('')
  const [section, setSection] = useState('')
  const [loading, setLoading] = useState(false)
  const [generatedCode, setGeneratedCode] = useState('')
  const [copied, setCopied] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')

  if (!open) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setErrorMsg('')
    try {
      const result = await onAdd(name, section)
      if (!result || !result.unique_code) throw new Error('Invalid response from server')
      setGeneratedCode(result.unique_code)
    } catch (err: any) {
      setErrorMsg(err?.message || 'Failed to add student')
    } finally {
      setLoading(false)
    }
  }

  const copyCode = async () => {
    await navigator.clipboard.writeText(generatedCode)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleDone = () => {
    setName('')
    setSection('')
    setGeneratedCode('')
    setCopied(false)
    onClose()
  }

  if (generatedCode) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4">
          <div className="px-6 py-4 border-b flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-800">Student Added</h2>
            <button onClick={handleDone} className="text-gray-400 hover:text-gray-600">
              <X className="w-5 h-5" />
            </button>
          </div>
          <div className="p-6 text-center space-y-4">
            <p className="text-sm text-gray-600">
              Share this code with <strong>{name}</strong>:
            </p>
            <div className="flex items-center justify-center gap-2 bg-gray-50 border-2 border-dashed border-indigo-300 rounded-lg px-4 py-3">
              <span className="text-2xl font-mono font-bold text-indigo-700 tracking-widest">
                {generatedCode}
              </span>
              <button
                onClick={copyCode}
                className="p-2 text-indigo-600 hover:bg-indigo-100 rounded-lg transition-colors"
                title="Copy code"
              >
                {copied ? <Check className="w-5 h-5 text-green-600" /> : <Copy className="w-5 h-5" />}
              </button>
            </div>
            <p className="text-xs text-gray-400">
              Student opens the ClassGuard desktop agent, enters this code, and is connected automatically.
            </p>
            <button
              onClick={handleDone}
              className="w-full px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
            >
              Done
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-lg font-semibold text-gray-800">Add Student</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Student Name</label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
              placeholder="Rahul Sharma"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Section</label>
            <input
              type="text"
              required
              value={section}
              onChange={(e) => setSection(e.target.value.toUpperCase())}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
              placeholder="S01"
            />
          </div>
          <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-3 text-sm text-indigo-800">
            After adding, a unique code will be generated. The student enters this code in their
            ClassGuard desktop agent to connect.
          </div>
          {errorMsg && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
              {errorMsg}
            </div>
          )}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
            >
              {loading ? 'Adding...' : 'Add Student'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

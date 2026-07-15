import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Shield } from 'lucide-react'
import { api } from '../services/api'
import { wsClient } from '../services/websocket'

export function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [isRegister, setIsRegister] = useState(false)
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    setSuccess('')
    try {
      if (isRegister) {
        await api.register(email, password)
        setSuccess('Registration successful! Signing in...')
        const data = await api.login(email, password)
        localStorage.setItem('token', data.access_token)
        wsClient.connect(data.access_token)
        navigate('/dashboard')
      } else {
        const data = await api.login(email, password)
        localStorage.setItem('token', data.access_token)
        wsClient.connect(data.access_token)
        navigate('/dashboard')
      }
    } catch (err: any) {
      setError(err.message || (isRegister ? 'Registration failed' : 'Login failed'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-900 to-purple-900 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-8">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-indigo-100 rounded-full mb-4">
            <Shield className="w-8 h-8 text-indigo-600" />
          </div>
          <h1 className="text-2xl font-bold text-gray-800">ClassGuard</h1>
          <p className="text-sm text-gray-500 mt-1">
            {isRegister ? 'Faculty Registration' : 'Faculty Dashboard'}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="bg-red-50 text-red-600 text-sm px-4 py-2 rounded-lg">{error}</div>
          )}
          {success && (
            <div className="bg-green-50 text-green-600 text-sm px-4 py-2 rounded-lg">{success}</div>
          )}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-4 py-2.5 border rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none"
              placeholder="faculty@college.edu"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-2.5 border rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {loading ? (isRegister ? 'Registering...' : 'Signing in...') : (isRegister ? 'Register Account' : 'Sign In')}
          </button>
          
          <div className="text-center mt-4">
            <button
              type="button"
              onClick={() => {
                setIsRegister(!isRegister)
                setError('')
                setSuccess('')
              }}
              className="text-sm text-indigo-600 hover:text-indigo-800 font-medium transition-colors"
            >
              {isRegister ? 'Already have an account? Sign In' : "Don't have an account? Register"}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

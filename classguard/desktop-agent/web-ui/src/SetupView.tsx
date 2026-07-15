import { useState } from "react";

interface Props {
  onConnect: (code: string, serverUrl: string) => Promise<void>;
  error: string;
}

export default function SetupView({ onConnect, error }: Props) {
  const [code, setCode] = useState("");
  const [serverUrl, setServerUrl] = useState("classguard-backend.onrender.com");
  const [loading, setLoading] = useState(false);
  const [showServer, setShowServer] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!code.trim()) return;
    setLoading(true);
    await onConnect(code.trim(), serverUrl.trim());
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 to-white flex items-center justify-center p-6">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-indigo-600 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg">
            <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">ClassGuard</h1>
          <p className="text-gray-500 mt-1">Student Desktop Agent</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-xl p-8 space-y-5">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Enter your unique code
            </label>
            <input
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase())}
              placeholder="CG-XXXXXX"
              className="w-full px-4 py-3 text-lg font-mono tracking-widest text-center border-2 border-gray-200 rounded-xl focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 outline-none transition-colors"
              autoFocus
              maxLength={9}
            />
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !code.trim()}
            className="w-full py-3 bg-indigo-600 text-white font-semibold rounded-xl hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-md"
          >
            {loading ? "Connecting..." : "Connect"}
          </button>

          <div className="pt-2">
            <button
              type="button"
              onClick={() => setShowServer(!showServer)}
              className="text-xs text-gray-400 hover:text-gray-600 underline"
            >
              {showServer ? "Hide" : "Show"} server settings
            </button>
            {showServer && (
              <div className="mt-3">
                <label className="block text-xs font-medium text-gray-500 mb-1">
                  Server Address (change if connecting over LAN)
                </label>
                <input
                  type="text"
                  value={serverUrl}
                  onChange={(e) => setServerUrl(e.target.value)}
                  placeholder="192.168.1.5:8000"
                  className="w-full px-3 py-2 text-sm font-mono border border-gray-200 rounded-lg focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 outline-none"
                />
              </div>
            )}
          </div>
        </form>

        <p className="text-center text-xs text-gray-400 mt-6">
          Ask your faculty for your unique code to connect
        </p>
      </div>
    </div>
  );
}

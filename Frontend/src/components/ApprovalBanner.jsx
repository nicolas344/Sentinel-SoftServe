import { useState } from 'react'
import { Zap, X, PauseCircle, CheckCircle2, Terminal } from 'lucide-react'
import { supabase } from '../lib/supabase'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function callApi(path, body) {
  const { data: { session } } = await supabase.auth.getSession()
  const res = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${session.access_token}`,
    },
    body: JSON.stringify(body),
  })
  const data = await res.json().catch(() => null)
  if (!res.ok) throw new Error(data?.detail || `Error ${res.status}`)
  return data
}

export default function ApprovalBanner({ incident, onApprove, loading, error }) {
  const [localLoading, setLocalLoading] = useState(null)
  const [localError, setLocalError] = useState(null)

  if (!incident?.proposed_action) return null

  const busy = loading || !!localLoading
  const displayError = error || localError

  const handleReject = async () => {
    setLocalLoading('reject')
    setLocalError(null)
    try {
      await callApi(`/api/incidents/${incident.id}/reject`, {})
    } catch (e) {
      setLocalError(e.message)
    } finally {
      setLocalLoading(null)
    }
  }

  const handlePostpone = async () => {
    setLocalLoading('postpone')
    setLocalError(null)
    try {
      await callApi(`/api/incidents/${incident.id}/postpone`, {})
    } catch (e) {
      setLocalError(e.message)
    } finally {
      setLocalLoading(null)
    }
  }

  const handleApprove = async () => {
    setLocalLoading('approve')
    setLocalError(null)
    try {
      await onApprove(incident.proposed_action)
    } catch (e) {
      setLocalError(e.message)
    } finally {
      setLocalLoading(null)
    }
  }

  return (
    <div className="mx-5 mb-4 rounded-xl border border-cyan-500/30 bg-cyan-950/60 overflow-hidden animate-approval-glow">
      {/* Header stripe */}
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-cyan-500/20 bg-cyan-500/5">
        <Zap className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
        <p className="text-xs font-semibold text-cyan-300 tracking-wide uppercase">
          Acción propuesta por el agente
        </p>
      </div>

      <div className="p-4">
        {/* Command */}
        <div className="flex items-start gap-2 mb-4">
          <Terminal className="w-3.5 h-3.5 text-slate-500 shrink-0 mt-0.5" />
          <pre className="flex-1 text-sm text-sky-300 font-mono bg-slate-950/80 border border-slate-800 rounded-lg px-3 py-2.5 overflow-x-auto whitespace-pre-wrap">
            {incident.proposed_action}
          </pre>
        </div>

        {displayError && (
          <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 mb-3">
            {displayError}
          </p>
        )}

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          <button
            onClick={handleReject}
            disabled={busy}
            className="flex items-center gap-1.5 border border-red-800/50 bg-red-950/40 hover:bg-red-900/50 disabled:opacity-50 text-red-400 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors"
          >
            <X className="w-3.5 h-3.5" />
            {localLoading === 'reject' ? 'Rechazando…' : 'Rechazar'}
          </button>

          <button
            onClick={handlePostpone}
            disabled={busy}
            className="flex items-center gap-1.5 border border-slate-700 bg-slate-800/50 hover:bg-slate-700 disabled:opacity-50 text-slate-300 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors"
          >
            <PauseCircle className="w-3.5 h-3.5" />
            {localLoading === 'postpone' ? 'Posponiendo…' : 'Posponer 30min'}
          </button>

          <button
            onClick={handleApprove}
            disabled={busy}
            className="ml-auto flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg px-4 py-1.5 text-xs font-semibold transition-colors"
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            {localLoading === 'approve' || loading ? 'Aprobando…' : 'Aprobar y ejecutar'}
          </button>
        </div>
      </div>
    </div>
  )
}

import { useState } from 'react'
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

  const busy = loading || !!localLoading
  const displayError = error || localError

  return (
    <div className="mx-6 mb-4 bg-cyan-950 border border-cyan-500/30 rounded-lg p-4">
      <p className="text-xs font-semibold text-cyan-300 uppercase tracking-wider mb-2">
        ⚡ Acción propuesta por el agente
      </p>
      <pre className="bg-slate-950 border border-slate-800 rounded-md px-3 py-2.5 text-xs text-sky-300 font-mono overflow-x-auto whitespace-pre-wrap mb-4">
        $ {incident.proposed_action}
      </pre>

      {displayError && (
        <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/25 rounded-md px-3 py-2 mb-3">
          {displayError}
        </p>
      )}

      <div className="flex items-center gap-2 flex-wrap">
        <button
          onClick={handleReject}
          disabled={busy}
          className="border border-red-800/50 bg-red-900/30 hover:bg-red-900/60 disabled:opacity-50 text-red-400 rounded-md px-3.5 py-1.5 text-xs font-medium transition-colors"
        >
          {localLoading === 'reject' ? 'Rechazando…' : '✗ Rechazar'}
        </button>
        <button
          onClick={handlePostpone}
          disabled={busy}
          className="border border-slate-700 bg-slate-800/50 hover:bg-slate-700 disabled:opacity-50 text-slate-300 rounded-md px-3.5 py-1.5 text-xs font-medium transition-colors"
        >
          {localLoading === 'postpone' ? 'Posponiendo…' : '⏸ Posponer 30min'}
        </button>
        <button
          onClick={handleApprove}
          disabled={busy}
          className="ml-auto bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-md px-4 py-1.5 text-xs font-medium transition-colors"
        >
          {localLoading === 'approve' || loading ? 'Aprobando…' : '✓ Aprobar y ejecutar'}
        </button>
      </div>
    </div>
  )
}

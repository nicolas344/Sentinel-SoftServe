import { useState, useEffect } from 'react'
import { supabase } from '../lib/supabase'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const RISK_BY_TYPE = {
  oom:                 { level: 'Alto',  color: 'text-orange-400', bg: 'bg-orange-500/10 border-orange-500/25' },
  app_crash:           { level: 'Alto',  color: 'text-orange-400', bg: 'bg-orange-500/10 border-orange-500/25' },
  restart_loop:        { level: 'Alto',  color: 'text-orange-400', bg: 'bg-orange-500/10 border-orange-500/25' },
  config_error:        { level: 'Medio', color: 'text-yellow-400', bg: 'bg-yellow-500/10 border-yellow-500/25' },
  dependency_failure:  { level: 'Medio', color: 'text-yellow-400', bg: 'bg-yellow-500/10 border-yellow-500/25' },
  network_issue:       { level: 'Medio', color: 'text-yellow-400', bg: 'bg-yellow-500/10 border-yellow-500/25' },
}

function getRisk(incidentType, command) {
  if (command?.includes('logs')) return { level: 'Bajo', color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/25' }
  return RISK_BY_TYPE[incidentType] || { level: 'Medio', color: 'text-yellow-400', bg: 'bg-yellow-500/10 border-yellow-500/25' }
}

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

export default function ApprovalModal({ incident, onApprove, onClose }) {
  const [comment, setComment] = useState('')
  const [loading, setLoading] = useState(null) // 'approve' | 'reject' | 'postpone'
  const [error, setError] = useState(null)

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const risk = getRisk(incident.incident_type, incident.proposed_action)

  const handle = async (action) => {
    setLoading(action)
    setError(null)
    try {
      if (action === 'approve') {
        await onApprove(comment)
      } else {
        await callApi(`/api/incidents/${incident.id}/${action}`, { comment })
      }
      onClose()
    } catch (e) {
      setError(e.message)
      setLoading(null)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

      <div className="relative w-full max-w-lg bg-slate-900 border border-slate-700 rounded-xl shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
          <div>
            <h2 className="text-sm font-semibold text-slate-100">Aprobar acción de alto riesgo</h2>
            <p className="text-xs text-slate-400 mt-0.5">Revisa los detalles antes de ejecutar</p>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300 transition-colors text-lg leading-none">×</button>
        </div>

        <div className="px-5 py-4 space-y-4">
          {/* Detalles del incidente */}
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-slate-950 rounded-lg p-3">
              <p className="text-xs text-slate-500 mb-1">Servicio afectado</p>
              <p className="text-xs text-slate-200 font-mono truncate">{incident.target}</p>
            </div>
            <div className="bg-slate-950 rounded-lg p-3">
              <p className="text-xs text-slate-500 mb-1">Tipo de incidente</p>
              <p className="text-xs text-slate-200">{incident.incident_type || '—'}</p>
            </div>
          </div>

          {/* Nivel de riesgo */}
          <div className={`flex items-center gap-2 px-3 py-2 rounded-lg border ${risk.bg}`}>
            <span className="text-xs text-slate-400">Nivel de riesgo:</span>
            <span className={`text-xs font-semibold ${risk.color}`}>{risk.level}</span>
            {risk.level === 'Alto' && (
              <span className="text-xs text-slate-400 ml-1">— El reinicio interrumpirá el servicio brevemente.</span>
            )}
          </div>

          {/* Comando */}
          <div>
            <p className="text-xs text-slate-500 mb-1.5">Comando a ejecutar</p>
            <pre className="bg-slate-950 border border-slate-800 rounded-lg p-3 text-xs text-sky-300 font-mono">
              {incident.proposed_action}
            </pre>
          </div>

          {/* Comentario */}
          <div>
            <label className="text-xs text-slate-500 block mb-1.5">
              Comentario <span className="text-slate-600">(opcional)</span>
            </label>
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Ej: Aprobado tras verificar que no hay tráfico activo..."
              rows={2}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-slate-500 resize-none"
            />
          </div>

          {error && (
            <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/25 rounded-lg px-3 py-2">
              {error}
            </p>
          )}
        </div>

        {/* Acciones */}
        <div className="flex gap-2 px-5 pb-5">
          <button
            onClick={() => handle('approve')}
            disabled={!!loading}
            className="flex-1 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg px-4 py-2 text-xs font-medium transition-colors"
          >
            {loading === 'approve' ? 'Aprobando...' : '✓ Aprobar'}
          </button>
          <button
            onClick={() => handle('postpone')}
            disabled={!!loading}
            className="flex-1 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed text-slate-200 rounded-lg px-4 py-2 text-xs font-medium transition-colors"
          >
            {loading === 'postpone' ? 'Posponiendo...' : '⏸ Posponer'}
          </button>
          <button
            onClick={() => handle('reject')}
            disabled={!!loading}
            className="flex-1 bg-red-900/40 hover:bg-red-900/70 disabled:opacity-50 disabled:cursor-not-allowed text-red-400 border border-red-800/50 rounded-lg px-4 py-2 text-xs font-medium transition-colors"
          >
            {loading === 'reject' ? 'Rechazando...' : '✗ Rechazar'}
          </button>
        </div>
      </div>
    </div>
  )
}

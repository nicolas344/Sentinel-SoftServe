import { useState, useEffect } from 'react'
import { supabase } from '../lib/supabase'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const SEVERITY_COLORS = {
  critical: 'text-red-400',
  high: 'text-orange-400',
  medium: 'text-yellow-400',
  low: 'text-slate-400',
}

function timeAgo(isoString) {
  if (!isoString) return '—'
  const diff = Date.now() - new Date(isoString).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `hace ${mins}m`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `hace ${hrs}h`
  return `hace ${Math.floor(hrs / 24)}d`
}

export default function SimilarIncidentsCard({ incidentId, onApplySolution }) {
  const [similar, setSimilar] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const { data: { session } } = await supabase.auth.getSession()
        const res = await fetch(`${API_URL}/api/incidents/${incidentId}/similar`, {
          headers: { Authorization: `Bearer ${session.access_token}` },
        })
        if (!res.ok) throw new Error('Error al cargar incidentes similares')
        const data = await res.json()
        if (!cancelled) setSimilar(data)
      } catch (e) {
        if (!cancelled) setError(e.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [incidentId])

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-xs text-slate-500 py-2">
        <span className="w-3 h-3 rounded-full border-2 border-slate-600 border-t-slate-400 animate-spin" />
        Buscando incidentes similares...
      </div>
    )
  }

  if (error) {
    return (
      <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-md px-3 py-2">
        {error}
      </p>
    )
  }

  if (similar.length === 0) {
    return null
  }

  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Incidentes similares</p>
      {similar.map((item) => {
        const meta = item.metadata || {}
        const tools = meta.tools_used ? meta.tools_used.split(',').filter(Boolean) : []
        return (
          <div key={item.id} className="bg-slate-900 border border-slate-800 rounded-lg p-3 space-y-2">
            <div className="flex items-start justify-between gap-2">
              <p className="text-xs font-medium text-slate-200 leading-snug">{meta.title || 'Incidente anterior'}</p>
              <span className={`text-xs shrink-0 ${SEVERITY_COLORS[meta.severity] || 'text-slate-400'}`}>
                {meta.severity || '—'}
              </span>
            </div>

            <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-500">
              <span>Tipo: <span className="text-slate-400">{meta.incident_type || '—'}</span></span>
              <span>Target: <span className="text-slate-400 font-mono">{meta.target || '—'}</span></span>
              <span>{timeAgo(meta.stored_at)}</span>
            </div>

            {tools.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {tools.map((t) => (
                  <span key={t} className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 text-xs font-mono">
                    {t}
                  </span>
                ))}
              </div>
            )}

            {onApplySolution && meta.proposed_action && (
              <button
                onClick={() => onApplySolution(item)}
                className="text-xs text-sky-400 hover:text-sky-300 transition-colors"
              >
                Aplicar misma solución →
              </button>
            )}
          </div>
        )
      })}
    </div>
  )
}

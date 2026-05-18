import { useEffect, useMemo, useState } from 'react'
import {
  exportPostMortemMarkdown,
  exportPostMortemPdf,
  fetchPostMortem,
  savePostMortem,
} from '../services/incidentExports'

function fmtDate(value) {
  if (!value) return 'No disponible'
  return new Date(value).toLocaleString('es-CO', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function PostMortemEditor({ incident }) {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [content, setContent] = useState('')
  const [updatedAt, setUpdatedAt] = useState(null)

  const isResolved = incident?.status === 'resolved'

  useEffect(() => {
    let cancelled = false

    async function load() {
      if (!incident?.id) return
      setLoading(true)
      setError(null)
      try {
        const data = await fetchPostMortem(incident.id)
        if (!cancelled) {
          setContent(data.content || '')
          setUpdatedAt(data.updated_at || null)
        }
      } catch (e) {
        if (!cancelled) setError(e.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => { cancelled = true }
  }, [incident?.id])

  const contentSize = useMemo(() => content.length.toLocaleString('es-CO'), [content])

  const onSave = async () => {
    setSaving(true)
    setError(null)
    try {
      await savePostMortem(incident.id, content)
      setUpdatedAt(new Date().toISOString())
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  if (!incident?.id) return null

  if (!isResolved) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
        <p className="text-xs text-slate-500">
          El post-mortem se genera automáticamente cuando el incidente cambia a estado resuelto.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Post-Mortem</p>
          <p className="text-[11px] text-slate-600 mt-1">
            Última actualización: {fmtDate(updatedAt)} · {contentSize} caracteres
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => exportPostMortemMarkdown(content, incident.title)}
            disabled={!content || loading}
            className="text-xs px-3 py-1.5 rounded-lg border border-slate-700 text-slate-300 hover:border-slate-500 disabled:opacity-50 transition-colors"
          >
            Exportar .md
          </button>
          <button
            onClick={() => exportPostMortemPdf(content, incident.title)}
            disabled={!content || loading}
            className="text-xs px-3 py-1.5 rounded-lg border border-slate-700 text-slate-300 hover:border-slate-500 disabled:opacity-50 transition-colors"
          >
            Exportar PDF
          </button>
          <button
            onClick={onSave}
            disabled={saving || loading || !content.trim()}
            className="text-xs px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-50 transition-colors"
          >
            {saving ? 'Guardando...' : 'Guardar'}
          </button>
        </div>
      </div>

      {error && (
        <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-md px-3 py-2">
          {error}
        </p>
      )}

      {loading ? (
        <div className="flex items-center gap-2 text-xs text-slate-500 py-4">
          <span className="w-3 h-3 rounded-full border-2 border-slate-600 border-t-slate-400 animate-spin" />
          Generando post-mortem...
        </div>
      ) : (
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          className="w-full min-h-[520px] bg-slate-950 border border-slate-800 rounded-xl p-4 text-xs text-slate-200 font-mono leading-relaxed focus:outline-none focus:border-slate-600 resize-y"
          placeholder="El post-mortem aparecerá aquí..."
        />
      )}
    </div>
  )
}

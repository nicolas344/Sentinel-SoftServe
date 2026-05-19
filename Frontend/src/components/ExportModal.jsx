import { useState } from 'react'
import { fetchIncidentExport, triggerTextDownload } from '../services/incidentExports'

export default function ExportModal({ incident, onClose }) {
  const [loading, setLoading] = useState(null)
  const [error, setError] = useState(null)

  const handleExport = async (format) => {
    if (!incident?.id) return
    setLoading(format)
    setError(null)
    try {
      const { content, extension } = await fetchIncidentExport(incident.id, format)
      const safeTitle = String(incident.title || incident.id).replace(/[^a-zA-Z0-9_-]/g, '_')
      const filename = `incident_${safeTitle}_${incident.id.slice(0, 8)}.${extension}`
      const mime = format === 'json' ? 'application/json;charset=utf-8' : 'text/markdown;charset=utf-8'
      triggerTextDownload(content, filename, mime)
      onClose()
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(null)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-md bg-slate-900 border border-slate-700 rounded-xl shadow-2xl p-5 space-y-4">
        <div className="flex items-start justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold text-slate-100">Exportar incidente</h3>
            <p className="text-xs text-slate-500 mt-1">Selecciona el formato para descargar inmediatamente.</p>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300 text-lg leading-none">×</button>
        </div>

        <div className="bg-slate-950 border border-slate-800 rounded-lg p-3">
          <p className="text-xs text-slate-500">Incidente</p>
          <p className="text-xs text-slate-200 mt-1 truncate" title={incident?.title}>{incident?.title || '—'}</p>
          <p className="text-[11px] text-slate-600 mt-1 font-mono">{incident?.id || '—'}</p>
        </div>

        {error && (
          <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
            {error}
          </p>
        )}

        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={() => handleExport('json')}
            disabled={!!loading}
            className="bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white rounded-lg px-3 py-2 text-xs font-semibold transition-colors"
          >
            {loading === 'json' ? 'Exportando...' : 'Exportar JSON'}
          </button>
          <button
            onClick={() => handleExport('markdown')}
            disabled={!!loading}
            className="bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-slate-100 rounded-lg px-3 py-2 text-xs font-semibold transition-colors"
          >
            {loading === 'markdown' ? 'Exportando...' : 'Exportar Markdown'}
          </button>
        </div>
      </div>
    </div>
  )
}

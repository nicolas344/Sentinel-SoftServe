const SEVERITY_CONFIG = {
  critical: { dot: 'bg-red-500',    badge: 'bg-red-500/15 text-red-400 border border-red-500/25' },
  high:     { dot: 'bg-orange-500', badge: 'bg-orange-500/15 text-orange-400 border border-orange-500/25' },
  medium:   { dot: 'bg-yellow-500', badge: 'bg-yellow-500/15 text-yellow-400 border border-yellow-500/25' },
  low:      { dot: 'bg-green-500',  badge: 'bg-green-500/15 text-green-400 border border-green-500/25' },
}

const SEVERITY_LABELS = { critical: 'Crítico', high: 'Alto', medium: 'Medio', low: 'Bajo' }

const STATUS_CONFIG = {
  detected:           { label: 'Detectado',          className: 'bg-blue-500/15 text-blue-400' },
  investigating:      { label: 'Investigando',        className: 'bg-purple-500/15 text-purple-400' },
  analyzed:           { label: 'Analizado',           className: 'bg-amber-500/15 text-amber-400' },
  awaiting_approval:  { label: 'Esperando aprobación', className: 'bg-cyan-500/15 text-cyan-400' },
  executing_solution: { label: 'Ejecutando solución', className: 'bg-indigo-500/15 text-indigo-300' },
  verifying:          { label: 'Verificando',         className: 'bg-teal-500/15 text-teal-300' },
  resolved:           { label: 'Resuelto',            className: 'bg-emerald-500/15 text-emerald-400' },
  failed:             { label: 'Falló',               className: 'bg-red-500/15 text-red-400' },
}

const RUNTIME_CONFIG = {
  docker:   { label: 'docker',   className: 'bg-blue-900/40 text-blue-400' },
  podman:   { label: 'podman',   className: 'bg-purple-900/40 text-purple-400' },
  database: { label: 'database', className: 'bg-amber-900/40 text-amber-400' },
}

function formatDate(dateStr) {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleString('es-CO', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

export default function IncidentCard({ incident, isSelected, onClick }) {
  const severityCfg  = SEVERITY_CONFIG[incident.severity] || SEVERITY_CONFIG.medium
  const statusCfg    = STATUS_CONFIG[incident.status] || STATUS_CONFIG.detected
  const runtimeKey   = incident.source_type === 'database' ? 'database' : incident.container_runtime
  const runtimeCfg   = RUNTIME_CONFIG[runtimeKey]
  const needsApproval = incident.status === 'awaiting_approval'

  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-6 py-4 hover:bg-slate-900/60 transition-colors ${
        isSelected ? 'bg-slate-900' : ''
      }`}
    >
      <div className="flex items-start gap-3">
        <span className={`inline-block w-2 h-2 rounded-full shrink-0 mt-[5px] ${severityCfg.dot}`} />
        <div className="flex-1 min-w-0">
          <p className="text-sm text-slate-200 leading-snug truncate">{incident.title}</p>
          <p className="text-xs text-slate-500 mt-1 truncate">
            {incident.target}
            {incident.server_name ? ` · ${incident.server_name}` : ''}
          </p>
          <div className="flex items-center gap-2 mt-2 flex-wrap">
            <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${severityCfg.badge}`}>
              {SEVERITY_LABELS[incident.severity] || incident.severity}
            </span>
            <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${statusCfg.className}`}>
              {statusCfg.label}
            </span>
            {runtimeCfg && (
              <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono ${runtimeCfg.className}`}>
                {runtimeCfg.label}
              </span>
            )}
            <span className="text-xs text-slate-600 ml-auto">{formatDate(incident.created_at)}</span>
          </div>
          {needsApproval && (
            <div className="mt-2">
              <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium bg-cyan-500/15 text-cyan-300 border border-cyan-500/25 animate-pulse">
                ⚡ Acción requerida
              </span>
            </div>
          )}
        </div>
      </div>
    </button>
  )
}

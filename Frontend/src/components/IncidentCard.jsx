import { Zap, Clock, Timer } from 'lucide-react'

function formatMTTR(created, resolved) {
  if (!created || !resolved) return null
  const ms = new Date(resolved) - new Date(created)
  if (ms < 0) return null
  const mins = Math.floor(ms / 60000)
  const secs = Math.floor((ms % 60000) / 1000)
  if (mins < 1) return `${secs}s`
  if (mins < 60) return `${mins}m ${secs}s`
  const hrs = Math.floor(mins / 60)
  return `${hrs}h ${mins % 60}m`
}

function truncateTitle(title, max = 55) {
  if (!title) return '—'
  if (title.length <= max) return title
  return title.slice(0, max - 1) + '…'
}

const SEVERITY = {
  critical: {
    border:  'border-l-red-500',
    dot:     'bg-red-500',
    badge:   'bg-red-500/10 text-red-400 border border-red-500/20',
    label:   'Crítico',
    glow:    'shadow-red-500/10',
  },
  high: {
    border:  'border-l-orange-500',
    dot:     'bg-orange-500',
    badge:   'bg-orange-500/10 text-orange-400 border border-orange-500/20',
    label:   'Alto',
    glow:    'shadow-orange-500/10',
  },
  medium: {
    border:  'border-l-yellow-500',
    dot:     'bg-yellow-500',
    badge:   'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20',
    label:   'Medio',
    glow:    '',
  },
  low: {
    border:  'border-l-green-500',
    dot:     'bg-green-500',
    badge:   'bg-green-500/10 text-green-400 border border-green-500/20',
    label:   'Bajo',
    glow:    '',
  },
}

const STATUS = {
  detected:           { label: 'Detectado',     color: 'text-blue-400' },
  investigating:      { label: 'Investigando',   color: 'text-purple-400' },
  analyzed:           { label: 'Analizado',      color: 'text-amber-400' },
  awaiting_approval:  { label: 'Aprobar',        color: 'text-cyan-400' },
  executing_solution: { label: 'Ejecutando',     color: 'text-indigo-300' },
  verifying:          { label: 'Verificando',    color: 'text-teal-300' },
  resolved:           { label: 'Resuelto',       color: 'text-emerald-400' },
  failed:             { label: 'Falló',          color: 'text-red-400' },
}

const RUNTIME = {
  docker:   'docker',
  podman:   'podman',
  database: 'db',
}

function timeAgo(dateStr) {
  if (!dateStr) return null
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'ahora'
  if (mins < 60) return `${mins}m`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h`
  return `${Math.floor(hrs / 24)}d`
}

export default function IncidentCard({ incident, isSelected, onClick }) {
  const sev    = SEVERITY[incident.severity] || SEVERITY.medium
  const status = STATUS[incident.status] || STATUS.detected
  const rt     = incident.source_type === 'database' ? 'database' : incident.container_runtime
  const rtLabel = RUNTIME[rt]
  const needsApproval = incident.status === 'awaiting_approval'
  const isResolved    = incident.status === 'resolved'
  const ago  = timeAgo(incident.created_at)
  const mttr = isResolved ? formatMTTR(incident.created_at, incident.executed_at) : null

  return (
    <button
      onClick={onClick}
      className={`
        w-full text-left border-l-[3px] ${sev.border}
        px-4 py-3.5 transition-all duration-150
        ${isSelected
          ? 'bg-slate-800/80 shadow-lg ' + sev.glow
          : 'hover:bg-slate-900/60'
        }
      `}
    >
      <div className="flex items-start gap-3">
        {/* Severity dot */}
        <span className={`mt-1.5 w-1.5 h-1.5 rounded-full shrink-0 ${sev.dot} ${incident.severity === 'critical' ? 'animate-pulse' : ''}`} />

        <div className="flex-1 min-w-0">
          {/* Title */}
          <p className="text-sm font-medium text-slate-200 leading-snug truncate" title={incident.title}>
            {truncateTitle(incident.title)}
          </p>

          {/* Target + meta */}
          <div className="flex items-center gap-2 mt-1 text-xs text-slate-500">
            <span className="font-mono truncate max-w-[120px]">{incident.target}</span>
            {rtLabel && (
              <>
                <span className="text-slate-700">·</span>
                <span>{rtLabel}</span>
              </>
            )}
            {ago && (
              <>
                <span className="text-slate-700">·</span>
                <span className="flex items-center gap-0.5 ml-auto shrink-0">
                  <Clock className="w-3 h-3" />
                  {ago}
                </span>
              </>
            )}
          </div>

          {/* Badges row */}
          <div className="flex items-center gap-1.5 mt-2 flex-wrap">
            <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium ${sev.badge}`}>
              {sev.label}
            </span>
            <span className={`text-[11px] font-medium ${status.color}`}>
              {status.label}
            </span>

            {needsApproval && (
              <span className="ml-auto inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-cyan-500/15 text-cyan-300 border border-cyan-500/25 animate-pulse">
                <Zap className="w-3 h-3" />
                Aprobar
              </span>
            )}

            {mttr && (
              <span className="ml-auto inline-flex items-center gap-1 text-[10px] text-emerald-500 font-medium">
                <Timer className="w-3 h-3" />
                {mttr}
              </span>
            )}
          </div>
        </div>
      </div>
    </button>
  )
}

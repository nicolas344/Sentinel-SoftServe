import { useMemo, useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'

// Orden canónico del ciclo de vida de un incidente
const STATUS_ORDER = [
  'detected',
  'investigating',
  'analyzed',
  'awaiting_approval',
  'executing_solution',
  'verifying',
  'resolved',
  'failed',
]

function statusIndex(status) {
  const idx = STATUS_ORDER.indexOf(status)
  return idx === -1 ? 0 : idx
}

function fmt(dateStr) {
  if (!dateStr) return null
  return new Date(dateStr).toLocaleString('es-CO', {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

function extractToolsFromReasoning(reasoning) {
  if (!reasoning) return []
  const match = reasoning.match(/Tools invocadas:\s*([^\n.]+)/i)
  if (!match) return []
  return match[1]
    .split(/[,—]/)
    .map((t) => t.replace(/`/g, '').trim())
    .filter((t) => t && t !== 'ninguna')
}

function buildEvents(incident, eventTimestamps = {}) {
  const current = statusIndex(incident.status)
  const isTerminal = incident.status === 'resolved' || incident.status === 'failed'
  const tools = extractToolsFromReasoning(incident.agent_reasoning)

  const reached = (s) => {
    if (isTerminal) return true
    return statusIndex(s) <= current
  }
  const isCurrent = (s) => !isTerminal && incident.status === s

  // Timestamp: usa la tabla incident_events si está disponible, si no cae en los campos del incidente
  const ts = (status, fallback) => fmt(eventTimestamps[status] || fallback || null)

  const events = []

  // 1. Detectado
  events.push({
    key: 'detected',
    label: 'Detectado',
    timestamp: ts('detected', incident.created_at),
    description: `Incidente creado · severidad ${incident.severity}${incident.server_name ? ` · ${incident.server_name}` : ''}`,
    done: reached('detected'),
    active: isCurrent('detected'),
    variant: 'blue',
  })

  // 2. Clasificando
  events.push({
    key: 'investigating',
    label: 'Clasificando',
    timestamp: ts('investigating', null),
    description: incident.incident_type
      ? `Tipo detectado: ${incident.incident_type}`
      : 'El agente está analizando el título, severidad y logs…',
    done: reached('investigating'),
    active: isCurrent('investigating'),
    variant: 'purple',
  })

  // 3. Investigado
  events.push({
    key: 'analyzed',
    label: 'Investigado',
    timestamp: ts('analyzed', null),
    description: tools.length > 0
      ? `Tools usadas: ${tools.map((t) => `\`${t}\``).join(', ')}`
      : incident.incident_type
        ? 'Análisis de causa raíz completado'
        : 'Pendiente de análisis',
    done: reached('analyzed'),
    active: isCurrent('analyzed'),
    variant: 'amber',
  })

  // 4. Esperando aprobación (solo si aplica)
  if (incident.proposed_action || statusIndex(incident.status) >= statusIndex('awaiting_approval')) {
    events.push({
      key: 'awaiting_approval',
      label: 'Esperando aprobación',
      timestamp: ts('awaiting_approval', null),
      description: incident.proposed_action
        ? `Acción propuesta: \`${incident.proposed_action}\``
        : 'Acción pendiente de revisión',
      done: reached('awaiting_approval'),
      active: isCurrent('awaiting_approval'),
      variant: 'cyan',
    })
  }

  // 5. Ejecutando (solo si pasó por esa etapa)
  if (incident.executed_at || statusIndex(incident.status) >= statusIndex('executing_solution')) {
    events.push({
      key: 'executing_solution',
      label: 'Acción ejecutada',
      timestamp: ts('executing_solution', incident.executed_at),
      description: incident.proposed_action
        ? `\`${incident.proposed_action}\``
        : 'Comando ejecutado',
      done: reached('executing_solution'),
      active: isCurrent('executing_solution'),
      variant: 'indigo',
    })
  }

  // 6. Verificando (solo si pasó por esa etapa)
  if (statusIndex(incident.status) >= statusIndex('verifying')) {
    events.push({
      key: 'verifying',
      label: 'Verificando servicio',
      timestamp: ts('verifying', null),
      description: 'El agente comprueba si el contenedor volvió a estado running',
      done: reached('verifying'),
      active: isCurrent('verifying'),
      variant: 'teal',
    })
  }

  // 7. Terminal: resuelto o falló
  if (incident.status === 'resolved') {
    events.push({
      key: 'resolved',
      label: 'Resuelto',
      timestamp: ts('resolved', incident.resolved_at),
      description: 'Servicio verificado y recuperado correctamente',
      done: true,
      active: false,
      variant: 'emerald',
    })
  } else if (incident.status === 'failed') {
    events.push({
      key: 'failed',
      label: 'Falló',
      timestamp: ts('failed', null),
      description: incident.action_error
        ? incident.action_error.replace(/^\[RECHAZADO\]\s*|^\[POSPUESTO\]\s*/i, '').slice(0, 120)
        : 'La acción no pudo completarse',
      done: true,
      active: false,
      variant: 'red',
    })
  }

  return events
}

const VARIANT_STYLES = {
  blue:    { dot: 'bg-blue-400',    ring: 'ring-blue-500/30',    label: 'text-blue-300',    line: 'bg-blue-500/20' },
  purple:  { dot: 'bg-purple-400',  ring: 'ring-purple-500/30',  label: 'text-purple-300',  line: 'bg-purple-500/20' },
  amber:   { dot: 'bg-amber-400',   ring: 'ring-amber-500/30',   label: 'text-amber-300',   line: 'bg-amber-500/20' },
  cyan:    { dot: 'bg-cyan-400',    ring: 'ring-cyan-500/30',    label: 'text-cyan-300',    line: 'bg-cyan-500/20' },
  indigo:  { dot: 'bg-indigo-400',  ring: 'ring-indigo-500/30',  label: 'text-indigo-300',  line: 'bg-indigo-500/20' },
  teal:    { dot: 'bg-teal-400',    ring: 'ring-teal-500/30',    label: 'text-teal-300',    line: 'bg-teal-500/20' },
  emerald: { dot: 'bg-emerald-400', ring: 'ring-emerald-500/30', label: 'text-emerald-300', line: 'bg-emerald-500/20' },
  red:     { dot: 'bg-red-400',     ring: 'ring-red-500/30',     label: 'text-red-300',     line: 'bg-red-500/20' },
}

function TimelineEvent({ event, isLast }) {
  const v = VARIANT_STYLES[event.variant] || VARIANT_STYLES.blue
  const pending = !event.done && !event.active

  // Split description on backtick blocks for monospace rendering
  function renderDesc(text) {
    if (!text) return null
    const parts = text.split(/(`[^`]+`)/)
    return parts.map((part, i) =>
      part.startsWith('`') && part.endsWith('`')
        ? <code key={i} className="text-[10px] font-mono bg-slate-800 px-1 py-0.5 rounded text-slate-300">{part.slice(1, -1)}</code>
        : <span key={i}>{part}</span>
    )
  }

  return (
    <div className="flex gap-3">
      {/* Dot + line */}
      <div className="flex flex-col items-center">
        <div
          className={`w-7 h-7 rounded-full flex items-center justify-center ring-2 shrink-0 transition-all ${
            pending
              ? 'bg-slate-900 ring-slate-800'
              : event.active
                ? `${v.dot.replace('bg-', 'bg-').replace('-400', '-500/20')} ${v.ring} ring-2`
                : `${v.dot.replace('-400', '-500/15')} ${v.ring}`
          }`}
        >
          {event.done && !event.active ? (
            <svg className={`w-3.5 h-3.5 ${pending ? 'text-slate-700' : v.label}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          ) : event.active ? (
            <span className={`w-2.5 h-2.5 rounded-full ${v.dot} animate-pulse`} />
          ) : (
            <span className="w-2 h-2 rounded-full bg-slate-700" />
          )}
        </div>
        {!isLast && (
          <div className={`w-px flex-1 mt-1 ${event.done ? v.line : 'bg-slate-800'}`} style={{ minHeight: '20px' }} />
        )}
      </div>

      {/* Content */}
      <div className={`pb-5 min-w-0 flex-1 ${isLast ? 'pb-0' : ''}`}>
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`text-xs font-semibold ${pending ? 'text-slate-600' : v.label}`}>
            {event.label}
          </span>
          {event.timestamp && (
            <span className="text-[10px] text-slate-600 font-mono">{event.timestamp}</span>
          )}
          {event.active && (
            <span className={`text-[10px] px-1.5 py-0.5 rounded-full border ${v.ring} ${v.label} bg-slate-900`}>
              en curso
            </span>
          )}
        </div>
        {event.description && (
          <p className={`text-[11px] mt-0.5 leading-relaxed ${pending ? 'text-slate-700' : 'text-slate-400'}`}>
            {renderDesc(event.description)}
          </p>
        )}
      </div>
    </div>
  )
}

export default function IncidentTimeline({ incident }) {
  const [eventTimestamps, setEventTimestamps] = useState({})

  useEffect(() => {
    let cancelled = false
    async function loadEvents() {
      const { data, error } = await supabase
        .from('incident_events')
        .select('status, occurred_at')
        .eq('incident_id', incident.id)
        .order('occurred_at', { ascending: true })
      if (error || cancelled) return
      const map = {}
      for (const row of data) {
        if (!map[row.status]) map[row.status] = row.occurred_at
      }
      setEventTimestamps(map)
    }
    loadEvents()
    return () => { cancelled = true }
  }, [incident.id])

  const events = useMemo(
    () => buildEvents(incident, eventTimestamps),
    [incident, eventTimestamps]
  )

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
      <div className="space-y-0">
        {events.map((event, i) => (
          <TimelineEvent key={event.key} event={event} isLast={i === events.length - 1} />
        ))}
      </div>
    </div>
  )
}

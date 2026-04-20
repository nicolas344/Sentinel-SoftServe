import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../contexts/useAuth'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import { useIncidentNotifications } from '../hooks/useIncidentNotifications'
import CreateIncidentModal from '../components/CreateIncidentModal'
import AgentReasoningPanel from '../components/AgentReasoningPanel'

const SEVERITY_CONFIG = {
  critical: { label: 'Crítico', dot: 'bg-red-500', badge: 'bg-red-500/15 text-red-400 border border-red-500/25' },
  high: { label: 'Alto', dot: 'bg-orange-500', badge: 'bg-orange-500/15 text-orange-400 border border-orange-500/25' },
  medium: { label: 'Medio', dot: 'bg-yellow-500', badge: 'bg-yellow-500/15 text-yellow-400 border border-yellow-500/25' },
  low: { label: 'Bajo', dot: 'bg-green-500', badge: 'bg-green-500/15 text-green-400 border border-green-500/25' },
}

const STATUS_CONFIG = {
  detected: { label: 'Detectado', className: 'bg-blue-500/15 text-blue-400' },
  investigating: { label: 'Investigando', className: 'bg-purple-500/15 text-purple-400' },
  analyzed: { label: 'Analizado', className: 'bg-amber-500/15 text-amber-400' },
  resolved: { label: 'Resuelto', className: 'bg-slate-500/15 text-slate-500' },
}

const TYPE_CONFIG = {
  app_crash: { label: 'App Crash', className: 'bg-red-500/10 text-red-400 border border-red-500/20' },
  oom: { label: 'OOM Killed', className: 'bg-orange-500/10 text-orange-400 border border-orange-500/20' },
  config_error: { label: 'Config Error', className: 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20' },
  dependency_failure: { label: 'Dependency Failure', className: 'bg-pink-500/10 text-pink-400 border border-pink-500/20' },
  unknown: { label: 'Desconocido', className: 'bg-slate-500/10 text-slate-400 border border-slate-500/20' },
  manual: { label: 'Manual', className: 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20' },
}

function SeverityDot({ severity }) {
  const color = SEVERITY_CONFIG[severity]?.dot || 'bg-slate-500'
  return <span className={`inline-block w-2 h-2 rounded-full shrink-0 mt-[5px] ${color}`} />
}

function SeverityBadge({ severity }) {
  const config = SEVERITY_CONFIG[severity] || SEVERITY_CONFIG.medium
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${config.badge}`}>
      {config.label}
    </span>
  )
}

function StatusBadge({ status }) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.detected
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${config.className}`}>
      {config.label}
    </span>
  )
}

function IncidentTypeBadge({ type }) {
  if (!type) return null
  const config = TYPE_CONFIG[type] || TYPE_CONFIG.unknown
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${config.className}`}>
      {config.label}
    </span>
  )
}

function formatDate(dateStr) {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleString('es-CO', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function MetaCard({ label, value, mono = false }) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-3">
      <p className="text-xs text-slate-500 mb-1">{label}</p>
      <p className={`text-sm text-slate-200 truncate ${mono ? 'font-mono' : ''}`}>{value || '—'}</p>
    </div>
  )
}

export default function Dashboard() {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [incidents, setIncidents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showCreateModal, setShowCreateModal] = useState(false)

  const selectedIncidentId = searchParams.get('incident')
  const selected = incidents.find((incident) => incident.id === selectedIncidentId) || null
  const {
    notificationsSupported,
    notificationPermission,
    askPermission,
    pushIncidentNotification,
    snoozed,
    snoozeUntilLabel,
    snoozeForMinutes,
    clearSnooze,
    refreshSnooze,
  } = useIncidentNotifications()

  const fetchIncidents = useCallback(async () => {
    setError(null)
    const { data, error: fetchError } = await supabase
      .from('incidents')
      .select('*')
      .order('created_at', { ascending: false })
      .limit(50)

    if (fetchError) {
      console.error('Error cargando incidentes:', fetchError)
      setError('No se pudieron cargar los incidentes.')
    } else {
      setIncidents(data || [])
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    // Initial bootstrap of incidents list; updates then come from Supabase Realtime.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchIncidents()

    const channel = supabase
      .channel('incidents-realtime')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'incidents' }, (payload) => {
        if (payload.eventType === 'INSERT') {
          setIncidents((prev) => {
            const exists = prev.some((incident) => incident.id === payload.new.id)
            return exists ? prev : [payload.new, ...prev]
          })
          pushIncidentNotification(payload.new)
        } else if (payload.eventType === 'UPDATE') {
          setIncidents((prev) => prev.map((i) => (i.id === payload.new.id ? payload.new : i)))
          pushIncidentNotification(payload.new)
        } else if (payload.eventType === 'DELETE') {
          setIncidents((prev) => prev.filter((i) => i.id !== payload.old.id))
          if (payload.old.id === selectedIncidentId) {
            setSearchParams({}, { replace: true })
          }
        }
      })
      .subscribe()

    return () => channel.unsubscribe()
  }, [fetchIncidents, pushIncidentNotification, selectedIncidentId, setSearchParams])

  useEffect(() => {
    refreshSnooze()
    const timer = window.setInterval(refreshSnooze, 30000)
    return () => window.clearInterval(timer)
  }, [refreshSnooze])

  const openIncident = (incident) => {
    setSearchParams({ incident: incident.id }, { replace: true })
  }

  const closeIncidentDetail = () => {
    setSearchParams({}, { replace: true })
  }

  const handleSignOut = async () => {
    await signOut()
    navigate('/login')
  }

  const criticalCount = incidents.filter(
    (i) => i.severity === 'critical' && i.status !== 'resolved'
  ).length

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50 flex flex-col">

      {/* Header */}
      <header className="flex items-center justify-between px-8 py-4 border-b border-slate-800 shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-bold">Sentinel</h1>
          <span className="text-slate-600 text-xs font-medium tracking-widest uppercase">
            Incident Triage
          </span>
          {criticalCount > 0 && (
            <span className="flex items-center gap-1.5 bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-medium px-2.5 py-1 rounded-full">
              <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse" />
              {criticalCount} crítico{criticalCount > 1 ? 's' : ''}
            </span>
          )}
        </div>
        <div className="flex items-center gap-4">
          {notificationsSupported && notificationPermission !== 'granted' && (
            <button
              onClick={askPermission}
              className="border border-blue-600/40 bg-blue-500/10 rounded-md px-3.5 py-1.5 text-blue-300 text-xs hover:border-blue-500 hover:text-blue-200 transition-colors"
            >
              Activar alertas del navegador
            </button>
          )}

          {notificationsSupported && notificationPermission === 'granted' && !snoozed && (
            <button
              onClick={() => snoozeForMinutes(15)}
              className="border border-slate-700 rounded-md px-3.5 py-1.5 text-slate-300 text-xs hover:border-slate-500 transition-colors"
            >
              Snooze 15m
            </button>
          )}

          {notificationsSupported && notificationPermission === 'granted' && snoozed && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-amber-300">Snooze hasta {snoozeUntilLabel}</span>
              <button
                onClick={clearSnooze}
                className="border border-amber-500/40 rounded-md px-3 py-1.5 text-amber-300 text-xs hover:border-amber-400 transition-colors"
              >
                Reactivar
              </button>
            </div>
          )}

          <span className="text-slate-500 text-sm">{user?.email}</span>
          <button
            onClick={handleSignOut}
            className="border border-slate-700 rounded-md px-3.5 py-1.5 text-slate-400 text-sm hover:border-slate-500 hover:text-slate-300 transition-colors"
          >
            Cerrar sesión
          </button>
        </div>
      </header>

      {/* Cuerpo */}
      <div className="flex flex-1 overflow-hidden">

        {/* Lista de incidentes */}
        <div
          className={`flex flex-col border-r border-slate-800 overflow-hidden transition-all duration-200 ${selected ? 'w-[420px] shrink-0' : 'flex-1'
            }`}
        >
          <div className="px-6 py-3 border-b border-slate-800 flex items-center justify-between">
            <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Incidentes
            </h2>
            <span className="text-xs text-slate-600">{incidents.length} registros</span>
            <button
              onClick={() => setShowCreateModal(true)}
              className="text-xs bg-blue-600 hover:bg-blue-500 text-white px-3 py-1 rounded-md font-medium transition-colors"
            >
              + Nuevo incidente
            </button>
          </div>

          {loading ? (
            <div className="flex-1 flex items-center justify-center">
              <p className="text-slate-600 text-sm">Cargando...</p>
            </div>
          ) : error ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-3 px-6 text-center">
              <p className="text-red-400 text-sm">{error}</p>
              <button
                onClick={fetchIncidents}
                className="text-slate-400 text-xs border border-slate-700 rounded px-3 py-1.5 hover:border-slate-500 transition-colors"
              >
                Reintentar
              </button>
            </div>
          ) : incidents.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-2 text-center px-6">
              <div className="w-8 h-8 rounded-full bg-slate-900 flex items-center justify-center text-slate-600">
                ✓
              </div>
              <p className="text-slate-500 text-sm">Sin incidentes activos</p>
              <p className="text-slate-700 text-xs">El sistema está monitoreando en tiempo real</p>
            </div>
          ) : (
            <div className="flex-1 overflow-y-auto divide-y divide-slate-800/50">
              {incidents.map((incident) => (
                <button
                  key={incident.id}
                  onClick={() => openIncident(incident)}
                  className={`w-full text-left px-6 py-4 hover:bg-slate-900/60 transition-colors ${
                    selected?.id === incident.id ? 'bg-slate-900' : ''
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <SeverityDot severity={incident.severity} />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-slate-200 leading-snug truncate">{incident.title}</p>
                      <p className="text-xs text-slate-500 mt-1 truncate">
                        {incident.container_name}
                        {incident.server_name ? ` · ${incident.server_name}` : ''}
                      </p>
                      <div className="flex items-center gap-2 mt-2">
                        <SeverityBadge severity={incident.severity} />
                        <StatusBadge status={incident.status} />
                        <IncidentTypeBadge type={incident.incident_type} />
                        <span className="text-xs text-slate-600 ml-auto">
                          {formatDate(incident.created_at)}
                        </span>
                      </div>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Panel de detalle */}
        {selected ? (
          <div className="flex-1 flex flex-col overflow-hidden">
            <div className="px-6 py-3 border-b border-slate-800 flex items-center justify-between gap-4">
              <h2 className="text-sm font-medium text-slate-200 truncate">{selected.title}</h2>
              <button
                onClick={closeIncidentDetail}
                className="text-slate-600 hover:text-slate-300 text-xl leading-none shrink-0 transition-colors"
                aria-label="Cerrar detalle"
              >
                ×
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-5">
              <div className="grid grid-cols-2 gap-3">
                <MetaCard label="Contenedor" value={selected.container_name} mono />
                <MetaCard label="Servidor" value={selected.server_name} />
                <MetaCard label="Detectado" value={formatDate(selected.created_at)} />
                <MetaCard label="Estado" value={STATUS_CONFIG[selected.status]?.label} />
              </div>

              <div className="flex items-center gap-2 flex-wrap">
                <SeverityBadge severity={selected.severity} />
                <StatusBadge status={selected.status} />
                <IncidentTypeBadge type={selected.incident_type} />
              </div>

              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                  Logs del contenedor
                </p>
                {selected.logs ? (
                  <pre className="bg-slate-900 border border-slate-800 rounded-lg p-4 text-xs text-slate-300 font-mono overflow-x-auto whitespace-pre-wrap max-h-[30rem] overflow-y-auto leading-relaxed">
                    {selected.logs}
                  </pre>
                ) : (
                  <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
                    <p className="text-xs text-slate-600">Sin logs disponibles para este incidente</p>
                  </div>
                )}
              </div>

              {(selected.agent_reasoning ||
                selected.status === 'investigating' ||
                selected.status === 'detected') && (
                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                    Razonamiento del agente
                  </p>
                  <AgentReasoningPanel
                    reasoning={selected.agent_reasoning}
                    status={selected.status}
                  />
                </div>
              )}
            </div>
          </div>
        ) : (
          incidents.length > 0 && (
            <div className="flex-1 hidden lg:flex items-center justify-center text-slate-700 text-sm">
              Selecciona un incidente para ver los detalles
            </div>
          )
        )}
      </div>

      {showCreateModal && <CreateIncidentModal onClose={() => setShowCreateModal(false)} />}
    </div>
  )
}

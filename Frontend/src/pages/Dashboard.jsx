import { useState, useEffect, useCallback } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import {
  Shield, Plus, Settings, Bell, BellOff, LogOut, Search,
  X, ChevronRight, CheckCircle2, XCircle, AlertTriangle,
  Loader2, Bot, BarChart2, BookOpen, History, Zap,
  Terminal, RefreshCw, Clock,
} from 'lucide-react'
import { useAuth } from '../contexts/useAuth'
import { supabase } from '../lib/supabase'
import { useIncidentNotifications } from '../hooks/useIncidentNotifications'
import IncidentCard from '../components/IncidentCard'
import CreateIncidentModal from '../components/CreateIncidentModal'
import AgentReasoningPanel from '../components/AgentReasoningPanel'
import RunbookViewer from '../components/RunbookViewer'
import SimilarIncidentsCard from '../components/SimilarIncidentsCard'
import ApprovalBanner from '../components/ApprovalBanner'
import IncidentTimeline from '../components/IncidentTimeline'
import MetricsPanel from '../components/MetricsPanel'
import PostMortemEditor from '../components/PostMortemEditor'
import ExportModal from '../components/ExportModal'
import WelcomeModal from '../components/WelcomeModal'
import { shouldShowWelcome } from '../components/shouldShowWelcome'
import CommandPalette from '../components/CommandPalette'
import { executeIncidentAction } from '../services/incidentActions'

// ── Helpers ────────────────────────────────────────────────────────────────

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

function truncateTitle(title, max = 70) {
  if (!title) return '—'
  if (title.length <= max) return title
  return title.slice(0, max - 1) + '…'
}

function ColoredLogs({ logs }) {
  if (!logs) return null
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 text-xs font-mono overflow-auto max-h-96 space-y-px leading-relaxed">
      {logs.split('\n').map((line, i) => {
        const up = line.toUpperCase()
        const color =
          /\b(ERROR|FATAL|CRITICAL|EXCEPTION|TRACEBACK|PANIC)\b/.test(up) ? 'text-red-300' :
          /\b(WARN|WARNING)\b/.test(up) ? 'text-yellow-300' :
          /\b(DEBUG)\b/.test(up) ? 'text-slate-600' :
          /\b(INFO)\b/.test(up) ? 'text-slate-400' :
          /^\d{4}-\d{2}-\d{2}/.test(line) ? 'text-sky-400/80' :
          'text-slate-300'
        return (
          <div key={i} className={`whitespace-pre-wrap break-all ${color}`}>{line || ' '}</div>
        )
      })}
    </div>
  )
}

const SEVERITY_ORDER   = { critical: 0, high: 1, medium: 2, low: 3 }
const TERMINAL         = new Set(['resolved', 'failed'])
const PAGE_SIZE        = 20

const SEVERITY_BADGE = {
  critical: 'bg-red-500/10 text-red-400 border border-red-500/20',
  high:     'bg-orange-500/10 text-orange-400 border border-orange-500/20',
  medium:   'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20',
  low:      'bg-green-500/10 text-green-400 border border-green-500/20',
}
const SEVERITY_LABEL   = { critical: 'Crítico', high: 'Alto', medium: 'Medio', low: 'Bajo' }

const STATUS_BADGE = {
  detected:           'bg-blue-500/10 text-blue-400',
  investigating:      'bg-purple-500/10 text-purple-400',
  analyzed:           'bg-amber-500/10 text-amber-400',
  awaiting_approval:  'bg-cyan-500/10 text-cyan-400',
  executing_solution: 'bg-indigo-500/10 text-indigo-300',
  verifying:          'bg-teal-500/10 text-teal-300',
  resolved:           'bg-emerald-500/10 text-emerald-400',
  failed:             'bg-red-500/10 text-red-400',
}
const STATUS_LABEL = {
  detected:           'Detectado',
  investigating:      'Investigando',
  analyzed:           'Analizado',
  awaiting_approval:  'Esperando aprobación',
  executing_solution: 'Ejecutando solución',
  verifying:          'Verificando',
  resolved:           'Resuelto',
  failed:             'Falló',
}

const RUNTIME_BADGE = {
  docker:   'bg-blue-900/40 text-blue-400',
  podman:   'bg-purple-900/40 text-purple-400',
  database: 'bg-amber-900/40 text-amber-400',
}

function Badge({ className, children }) {
  return <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${className}`}>{children}</span>
}

function formatDate(d) {
  if (!d) return '—'
  return new Date(d).toLocaleString('es-CO', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

// Compact horizontal status stepper
const STEPS = ['detected', 'investigating', 'analyzed', 'awaiting_approval', 'executing_solution', 'verifying']
const STEP_LABELS = {
  detected:           'Detectado',
  investigating:      'Investigando',
  analyzed:           'Analizado',
  awaiting_approval:  'Aprobación',
  executing_solution: 'Ejecutando',
  verifying:          'Verificando',
}

function StatusStepper({ status }) {
  const currentIdx    = STEPS.indexOf(status)
  const isTerminal    = TERMINAL.has(status)
  const isResolved    = status === 'resolved'
  const isFailed      = status === 'failed'

  return (
    <div className="flex items-center gap-1 flex-wrap">
      {STEPS.map((step, i) => {
        const done    = isTerminal || i < currentIdx
        const current = !isTerminal && i === currentIdx
        return (
          <div key={step} className="flex items-center gap-1">
            <div className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium border transition-colors ${
              done    ? 'bg-emerald-500/10 border-emerald-500/25 text-emerald-300'
              : current ? 'bg-sky-500/10 border-sky-500/30 text-sky-200'
              : 'bg-slate-900 border-slate-800 text-slate-600'
            }`}>
              <span className={`w-1 h-1 rounded-full ${done ? 'bg-emerald-400' : current ? 'bg-sky-400 animate-pulse' : 'bg-slate-700'}`} />
              {STEP_LABELS[step]}
            </div>
            {i < STEPS.length - 1 && <span className={`w-3 h-px ${done || current ? 'bg-slate-700' : 'bg-slate-800'}`} />}
          </div>
        )
      })}
      <span className="w-3 h-px bg-slate-800" />
      <div className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium border ${
        isResolved ? 'bg-emerald-500/10 border-emerald-500/25 text-emerald-300'
        : isFailed  ? 'bg-red-500/10 border-red-500/25 text-red-300'
        : 'bg-slate-900 border-slate-800 text-slate-600'
      }`}>
        <span className={`w-1 h-1 rounded-full ${isResolved ? 'bg-emerald-400' : isFailed ? 'bg-red-400' : 'bg-slate-700'}`} />
        {isFailed ? 'Falló' : 'Resuelto'}
      </div>
    </div>
  )
}

// ── Empty / loading state for Col 2 ──────────────────────────────────────

function EmptyDetail({ hasIncidents, onNew }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-6 px-12 text-center">
      {hasIncidents ? (
        <>
          <div className="flex items-center gap-3 text-slate-600">
            <div className="flex items-center gap-1.5 text-xs text-slate-600 animate-pulse">
              <ChevronRight className="w-4 h-4 rotate-180" />
              <span>de la lista</span>
            </div>
            <div className="w-px h-6 bg-slate-800" />
            <ChevronRight className="w-5 h-5 text-slate-700" />
          </div>
          <div>
            <p className="text-sm text-slate-400 font-medium">Selecciona un incidente</p>
            <p className="text-xs text-slate-600 mt-1">El análisis del agente aparecerá aquí</p>
          </div>
        </>
      ) : (
        <>
          <div className="w-16 h-16 rounded-2xl bg-sky-600/10 border border-sky-500/20 flex items-center justify-center">
            <Shield className="w-8 h-8 text-sky-500/60" />
          </div>
          <div>
            <p className="text-base font-semibold text-slate-300">Sentinel está listo</p>
            <p className="text-sm text-slate-600 mt-1 max-w-xs">El sistema está monitoreando en tiempo real. Puedes crear un incidente de prueba para ver cómo funciona el flujo.</p>
          </div>
          <div className="flex flex-col gap-2 w-full max-w-xs">
            <button
              onClick={onNew}
              className="flex items-center justify-center gap-2 bg-sky-600 hover:bg-sky-500 text-white rounded-xl px-4 py-2.5 text-sm font-medium transition-colors"
            >
              <Plus className="w-4 h-4" />
              Crear incidente de prueba
            </button>
            <Link
              to="/setup"
              className="flex items-center justify-center gap-2 text-slate-500 hover:text-slate-300 border border-slate-800 hover:border-slate-600 rounded-xl px-4 py-2.5 text-sm transition-colors"
            >
              <Settings className="w-4 h-4" />
              Verificar integraciones
            </Link>
          </div>
        </>
      )}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────

const CONTEXT_TABS = [
  { id: 'agent',    label: 'Agente',   Icon: Bot },
  { id: 'metrics',  label: 'Métricas', Icon: BarChart2 },
  { id: 'runbooks', label: 'Runbooks', Icon: BookOpen },
  { id: 'history',  label: 'Historial', Icon: History },
  { id: 'postmortem', label: 'Post-Mortem', Icon: BookOpen },
]

export default function Dashboard() {
  const { user, signOut }           = useAuth()
  const navigate                    = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  // Data
  const [incidents, setIncidents]   = useState([])
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState(null)

  // List UI
  const [statusFilter, setStatusFilter] = useState('active')
  const [displayLimit, setDisplayLimit] = useState(PAGE_SIZE)

  // Detail / action state
  const [actionLoading, setActionLoading] = useState(false)
  const [actionError, setActionError]     = useState(null)
  const [actionResponse, setActionResponse] = useState(null)
  const [contextTab, setContextTab]       = useState('agent')

  // Overlays
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showWelcome, setShowWelcome]         = useState(false)
  const [showCmdPalette, setShowCmdPalette]   = useState(false)
  const [showExportModal, setShowExportModal] = useState(false)

  const selectedId = searchParams.get('incident')
  const selected   = incidents.find((i) => i.id === selectedId) || null

  const {
    notificationsSupported, notificationPermission,
    askPermission, pushIncidentNotification,
    snoozed, snoozeUntilLabel, snoozeForMinutes, clearSnooze, refreshSnooze,
  } = useIncidentNotifications()

  // Check welcome on mount
  useEffect(() => {
    if (shouldShowWelcome()) setShowWelcome(true)
  }, [])

  // Global Cmd+K
  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setShowCmdPalette(true)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  // Fetch incidents
  const fetchIncidents = useCallback(async () => {
    setError(null)
    const { data, error: err } = await supabase
      .from('incidents')
      .select('*')
      .order('created_at', { ascending: false })
      .limit(500)
    if (err) { setError('No se pudieron cargar los incidentes.') }
    else     { setIncidents(data || []) }
    setLoading(false)
  }, [])

  useEffect(() => {
    fetchIncidents()
    const channel = supabase
      .channel('incidents-realtime')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'incidents' }, (payload) => {
        if (payload.eventType === 'INSERT') {
          setIncidents((prev) => prev.some((i) => i.id === payload.new.id) ? prev : [payload.new, ...prev])
          pushIncidentNotification(payload.new)
        } else if (payload.eventType === 'UPDATE') {
          setIncidents((prev) => prev.map((i) => i.id === payload.new.id ? { ...i, ...payload.new } : i))
          pushIncidentNotification(payload.new)
        } else if (payload.eventType === 'DELETE') {
          setIncidents((prev) => prev.filter((i) => i.id !== payload.old.id))
          if (payload.old.id === selectedId) setSearchParams({}, { replace: true })
        }
      })
      .subscribe()
    return () => channel.unsubscribe()
  }, [fetchIncidents, pushIncidentNotification, selectedId, setSearchParams])

  useEffect(() => {
    refreshSnooze()
    const t = window.setInterval(refreshSnooze, 30000)
    return () => window.clearInterval(t)
  }, [refreshSnooze])

  // Reset per-incident state on selection change
  useEffect(() => {
    setActionLoading(false)
    setActionError(null)
    setActionResponse(null)
    setContextTab('agent')
  }, [selectedId])

  // Reset pagination on filter change
  useEffect(() => { setDisplayLimit(PAGE_SIZE) }, [statusFilter])

  // ── Derived data ──────────────────────────────────────────────────────────

  const filteredIncidents = incidents
    .filter((i) => {
      if (statusFilter === 'active')   return !TERMINAL.has(i.status)
      if (statusFilter === 'resolved') return TERMINAL.has(i.status)
      return true
    })
    .slice()
    .sort((a, b) => {
      if (statusFilter === 'active') {
        return (SEVERITY_ORDER[a.severity] ?? 4) - (SEVERITY_ORDER[b.severity] ?? 4)
          || new Date(b.created_at) - new Date(a.created_at)
      }
      if (statusFilter === 'all') {
        // Activos antes que terminales
        const aT = TERMINAL.has(a.status) ? 1 : 0
        const bT = TERMINAL.has(b.status) ? 1 : 0
        if (aT !== bT) return aT - bT
        // Dentro de activos: severidad primero
        if (!aT) {
          return (SEVERITY_ORDER[a.severity] ?? 4) - (SEVERITY_ORDER[b.severity] ?? 4)
            || new Date(b.created_at) - new Date(a.created_at)
        }
        // Dentro de resueltos: más recientes primero
        return new Date(b.created_at) - new Date(a.created_at)
      }
      // Resueltos: fecha primero
      return new Date(b.created_at) - new Date(a.created_at)
    })

  const visibleIncidents = filteredIncidents.slice(0, displayLimit)
  const hasMore          = filteredIncidents.length > displayLimit
  const criticalCount    = incidents.filter((i) => i.severity === 'critical' && !TERMINAL.has(i.status)).length
  const activeCount      = incidents.filter((i) => !TERMINAL.has(i.status)).length
  const resolvedCount    = incidents.filter((i) => TERMINAL.has(i.status)).length

  const TAB_COUNTS = {
    active:   activeCount,
    all:      incidents.length,
    resolved: resolvedCount,
  }

  // ── Handlers ──────────────────────────────────────────────────────────────

  const openIncident    = (i)  => setSearchParams({ incident: i.id }, { replace: true })
  const closeDetail     = ()   => setSearchParams({}, { replace: true })
  const handleSignOut   = async () => { await signOut(); navigate('/login') }

  const handleApprove   = async (command) => {
    setActionLoading(true)
    setActionError(null)
    try {
      const res = await executeIncidentAction({ incidentId: selected.id, command })
      setActionResponse(res)
    } catch (err) {
      setActionError(err.message)
      throw err
    } finally {
      setActionLoading(false)
    }
  }

  // ── Runtime / type badges ─────────────────────────────────────────────────

  const rtKey    = selected ? (selected.source_type === 'database' ? 'database' : selected.container_runtime) : null
  const rtClass  = RUNTIME_BADGE[rtKey]

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col h-screen bg-slate-950 text-slate-50 overflow-hidden">

      {/* ── Global overlays ─────────────────────────────────────────────── */}
      {showWelcome && <WelcomeModal onClose={() => setShowWelcome(false)} />}

      <CommandPalette
        open={showCmdPalette}
        onClose={() => setShowCmdPalette(false)}
        incidents={incidents}
        onSelectIncident={(i) => { openIncident(i); setShowCmdPalette(false) }}
        onNewIncident={() => setShowCreateModal(true)}
      />

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <header className="h-14 shrink-0 flex items-center justify-between px-6 border-b border-slate-800 bg-slate-950/95 backdrop-blur-sm">
        {/* Left: brand + client + counters */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-sky-600/20 border border-sky-500/30 flex items-center justify-center">
              <Shield className="w-3.5 h-3.5 text-sky-400" />
            </div>
            <span className="text-sm font-bold text-slate-100">Sentinel</span>
          </div>

          <div className="hidden sm:flex items-center gap-1.5 pl-3 border-l border-slate-800">
            <img src="/softserve-logo.jpeg" alt="SoftServe" className="w-5 h-5 rounded-md object-cover opacity-90" />
            <a
              href="https://www.softserveinc.com/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[11px] text-slate-500 hover:text-slate-400 transition-colors font-medium"
            >
              SoftServe
            </a>
          </div>

          {activeCount > 0 && (
            <div className="flex items-center gap-2 pl-3 border-l border-slate-800">
              <span className="text-xs text-slate-500">{activeCount} activo{activeCount !== 1 ? 's' : ''}</span>
              {criticalCount > 0 && (
                <span className="flex items-center gap-1 bg-red-500/10 border border-red-500/20 text-red-400 text-[11px] font-medium px-2 py-0.5 rounded-full">
                  <span className="w-1 h-1 rounded-full bg-red-400 animate-pulse" />
                  {criticalCount} crítico{criticalCount > 1 ? 's' : ''}
                </span>
              )}
            </div>
          )}
        </div>

        {/* Center: command search button */}
        <button
          onClick={() => setShowCmdPalette(true)}
          className="hidden sm:flex items-center gap-2 bg-slate-900 border border-slate-800 hover:border-slate-600 rounded-lg px-3 py-1.5 text-sm text-slate-500 hover:text-slate-400 transition-colors"
        >
          <Search className="w-3.5 h-3.5" />
          <span className="text-xs">Buscar incidentes…</span>
          <kbd className="text-[10px] bg-slate-800 border border-slate-700 rounded px-1.5 py-0.5 font-mono ml-4">⌘K</kbd>
        </button>

        {/* Right: actions */}
        <div className="flex items-center gap-2">
          {notificationsSupported && notificationPermission !== 'granted' && (
            <button
              onClick={askPermission}
              className="flex items-center gap-1.5 border border-slate-700 rounded-lg px-3 py-1.5 text-slate-400 text-xs hover:border-slate-500 transition-colors"
            >
              <Bell className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Alertas</span>
            </button>
          )}

          {notificationsSupported && notificationPermission === 'granted' && !snoozed && (
            <button
              onClick={() => snoozeForMinutes(15)}
              title="Silenciar notificaciones del navegador por 15 minutos"
              className="flex items-center gap-1.5 border border-slate-700 rounded-lg px-3 py-1.5 text-slate-400 text-xs hover:border-slate-500 transition-colors"
            >
              <BellOff className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Snooze 15m</span>
            </button>
          )}

          {snoozed && (
            <button onClick={clearSnooze} className="text-xs text-amber-400 border border-amber-500/30 rounded-lg px-3 py-1.5 hover:border-amber-400 transition-colors">
              Snooze hasta {snoozeUntilLabel}
            </button>
          )}

          <Link
            to="/setup"
            className="flex items-center gap-1.5 border border-slate-700 rounded-lg px-3 py-1.5 text-slate-400 text-xs hover:border-slate-500 hover:text-slate-300 transition-colors"
            title="Estado del sistema"
          >
            <Settings className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Sistema</span>
          </Link>

          {user?.email && (
            <div className="hidden sm:flex items-center gap-1.5 text-xs text-slate-600 border-r border-slate-800 pr-2 mr-0.5">
              <div className="w-5 h-5 rounded-full bg-sky-600/20 border border-sky-500/30 flex items-center justify-center text-[10px] font-bold text-sky-400 shrink-0">
                {user.email[0].toUpperCase()}
              </div>
              <span className="hidden md:inline truncate max-w-[120px]" title={user.email}>
                {user.email}
              </span>
            </div>
          )}

          <button
            onClick={handleSignOut}
            title="Cerrar sesión"
            className="flex items-center gap-1.5 border border-slate-700 rounded-lg px-3 py-1.5 text-slate-400 text-xs hover:border-slate-500 hover:text-slate-300 transition-colors"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Salir</span>
          </button>
        </div>
      </header>

      {/* ── Body: 3-column layout ────────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">

        {/* ── Col 1: Incident list ──────────────────────────────────────── */}
        <div className="w-72 shrink-0 flex flex-col border-r border-slate-800 overflow-hidden">

          {/* List header */}
          <div className="shrink-0 px-4 pt-3 pb-0 border-b border-slate-800">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                Incidentes
              </h2>
              <button
                onClick={() => setShowCreateModal(true)}
                className="flex items-center gap-1 text-xs bg-sky-600 hover:bg-sky-500 text-white px-2.5 py-1 rounded-lg font-medium transition-colors"
              >
                <Plus className="w-3 h-3" />
                Nuevo
              </button>
            </div>

            {/* Status filter tabs */}
            <div className="flex">
              {[
                { id: 'active',   label: 'Activos' },
                { id: 'all',      label: 'Todos' },
                { id: 'resolved', label: 'Resueltos' },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setStatusFilter(tab.id)}
                  className={`flex-1 py-2 text-xs font-medium border-b-2 transition-colors flex items-center justify-center gap-1 ${
                    statusFilter === tab.id
                      ? 'border-sky-500 text-sky-400'
                      : 'border-transparent text-slate-500 hover:text-slate-300'
                  }`}
                >
                  {tab.label}
                  {TAB_COUNTS[tab.id] > 0 && (
                    <span className={`text-[10px] px-1 rounded font-mono ${
                      statusFilter === tab.id ? 'text-sky-500/70' : 'text-slate-700'
                    }`}>
                      {TAB_COUNTS[tab.id]}
                    </span>
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* List items */}
          {loading ? (
            <div className="flex-1 flex items-center justify-center">
              <Loader2 className="w-5 h-5 text-slate-600 animate-spin" />
            </div>
          ) : error ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-3 px-5 text-center">
              <AlertTriangle className="w-5 h-5 text-red-400" />
              <p className="text-red-400 text-sm">{error}</p>
              <button onClick={fetchIncidents} className="text-slate-400 text-xs border border-slate-700 rounded-lg px-3 py-1.5 hover:border-slate-500 transition-colors">
                Reintentar
              </button>
            </div>
          ) : visibleIncidents.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-2 text-center px-5">
              <CheckCircle2 className="w-6 h-6 text-slate-700" />
              <p className="text-slate-500 text-sm">
                {statusFilter === 'active' ? 'Sin incidentes activos' : statusFilter === 'resolved' ? 'Sin incidentes resueltos' : 'Sin incidentes'}
              </p>
              <p className="text-slate-700 text-xs">Monitoreando en tiempo real</p>
            </div>
          ) : (
            <div className="flex-1 overflow-y-auto">
              {/* Contador de posición */}
              {filteredIncidents.length > 0 && (
                <div className="px-4 py-1.5 text-[10px] text-slate-700 border-b border-slate-800/60 bg-slate-950/40">
                  Mostrando {visibleIncidents.length} de {filteredIncidents.length}
                </div>
              )}

              {/* Lista con separador en vista "Todos" */}
              {statusFilter === 'all' ? (
                <>
                  {visibleIncidents.filter((i) => !TERMINAL.has(i.status)).length > 0 && (
                    <>
                      <div className="px-4 py-1.5 text-[10px] font-semibold text-slate-600 uppercase tracking-wider bg-slate-950/60 border-b border-slate-800/40">
                        Activos
                      </div>
                      <div className="divide-y divide-slate-800/50">
                        {visibleIncidents.filter((i) => !TERMINAL.has(i.status)).map((incident) => (
                          <IncidentCard key={incident.id} incident={incident} isSelected={selected?.id === incident.id} onClick={() => openIncident(incident)} />
                        ))}
                      </div>
                    </>
                  )}
                  {visibleIncidents.filter((i) => TERMINAL.has(i.status)).length > 0 && (
                    <>
                      <div className="px-4 py-1.5 text-[10px] font-semibold text-slate-600 uppercase tracking-wider bg-slate-950/60 border-b border-slate-800/40 border-t border-slate-800/40 mt-1">
                        Resueltos
                      </div>
                      <div className="divide-y divide-slate-800/50">
                        {visibleIncidents.filter((i) => TERMINAL.has(i.status)).map((incident) => (
                          <IncidentCard key={incident.id} incident={incident} isSelected={selected?.id === incident.id} onClick={() => openIncident(incident)} />
                        ))}
                      </div>
                    </>
                  )}
                </>
              ) : (
                <div className="divide-y divide-slate-800/50">
                  {visibleIncidents.map((incident) => (
                    <IncidentCard
                      key={incident.id}
                      incident={incident}
                      isSelected={selected?.id === incident.id}
                      onClick={() => openIncident(incident)}
                    />
                  ))}
                </div>
              )}

              {hasMore && (
                <div className="px-4 py-3 border-t border-slate-800">
                  <button
                    onClick={() => setDisplayLimit((p) => p + PAGE_SIZE)}
                    className="w-full text-xs text-slate-600 hover:text-slate-400 border border-slate-800 hover:border-slate-700 rounded-lg py-2 transition-colors"
                  >
                    Cargar {Math.min(PAGE_SIZE, filteredIncidents.length - displayLimit)} más · {filteredIncidents.length - displayLimit} restantes
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* ── Col 2: Incident core detail ──────────────────────────────── */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden border-r border-slate-800">
          {selected ? (
            <>
              {/* Fixed incident header */}
              <div className="shrink-0 px-6 py-4 border-b border-slate-800">
                <div className="flex items-start justify-between gap-4 mb-3">
                  <div className="min-w-0">
                    <h2 className="text-base font-semibold text-slate-100 leading-snug" title={selected.title}>
                      {truncateTitle(selected.title)}
                    </h2>
                    <p className="text-xs text-slate-500 mt-0.5 font-mono truncate">
                      {selected.target}{selected.server_name ? ` · ${selected.server_name}` : ''}
                    </p>
                  </div>
                  <button
                    onClick={closeDetail}
                    className="p-1.5 rounded-lg text-slate-600 hover:text-slate-300 hover:bg-slate-800 transition-colors shrink-0 mt-0.5"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>

                <div className="flex items-center justify-end mb-3">
                  <button
                    onClick={() => setShowExportModal(true)}
                    className="text-xs border border-slate-700 rounded-lg px-3 py-1.5 text-slate-300 hover:border-slate-500 transition-colors"
                  >
                    Exportar incidente
                  </button>
                </div>

                {/* Badges */}
                <div className="flex items-center gap-2 flex-wrap mb-3">
                  {selected.severity && (
                    <Badge className={SEVERITY_BADGE[selected.severity]}>
                      {SEVERITY_LABEL[selected.severity]}
                    </Badge>
                  )}
                  {selected.status && (
                    <Badge className={STATUS_BADGE[selected.status]}>
                      {STATUS_LABEL[selected.status]}
                    </Badge>
                  )}
                  {rtClass && (
                    <Badge className={`${rtClass} font-mono`}>{rtKey}</Badge>
                  )}
                  <div className="ml-auto flex items-center gap-1 text-xs text-slate-600">
                    <Clock className="w-3 h-3" />
                    {formatDate(selected.created_at)}
                  </div>
                </div>

                {/* Status stepper */}
                <StatusStepper status={selected.status} />
              </div>

              {/* Scrollable core content */}
              <div className="flex-1 overflow-y-auto">

                {/* Approval banner — always near the top */}
                {selected.status === 'awaiting_approval' && selected.proposed_action && (
                  <div className="pt-4">
                    <ApprovalBanner
                      incident={selected}
                      onApprove={handleApprove}
                      loading={actionLoading}
                      error={actionError}
                    />
                  </div>
                )}

                {/* Action result / execution state */}
                {selected.status !== 'awaiting_approval' && (
                  <div className="px-6 py-4 space-y-3">

                    {selected.proposed_action && (
                      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                        <div className="flex items-center gap-2 mb-2">
                          <Terminal className="w-3.5 h-3.5 text-slate-500" />
                          <p className="text-xs text-slate-500">
                            {TERMINAL.has(selected.status) ? 'Comando ejecutado' : 'Comando propuesto'}
                          </p>
                        </div>
                        <pre className="text-sm text-sky-300 font-mono overflow-x-auto whitespace-pre-wrap">
                          {selected.proposed_action}
                        </pre>
                      </div>
                    )}

                    {selected.status === 'executing_solution' && (
                      <div className="flex items-center gap-2 text-indigo-300 text-sm">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Ejecutando comando…
                      </div>
                    )}

                    {selected.status === 'verifying' && (
                      <div className="flex items-start gap-3 bg-teal-500/10 border border-teal-500/20 rounded-xl px-4 py-3">
                        <Loader2 className="w-4 h-4 text-teal-300 animate-spin shrink-0 mt-0.5" />
                        <div>
                          <p className="text-sm text-teal-200 font-medium">Verificando recuperación…</p>
                          <p className="text-xs text-teal-400/70 mt-0.5">El agente comprueba que el servicio volvió a estado running.</p>
                        </div>
                      </div>
                    )}

                    {selected.status === 'resolved' && (
                      <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-xl px-4 py-3 space-y-1.5">
                        <div className="flex items-center gap-2 text-emerald-400 text-sm font-medium">
                          <CheckCircle2 className="w-4 h-4 shrink-0" />
                          {selected.executed_at ? 'Servicio verificado y recuperado' : 'Incidente resuelto'}
                        </div>
                        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500 pl-6">
                          {selected.executed_at && (
                            <span>Resuelto el {formatDate(selected.executed_at)}</span>
                          )}
                          {formatMTTR(selected.created_at, selected.executed_at || selected.updated_at) && (
                            <span className="text-emerald-500/80 font-medium">
                              MTTR: {formatMTTR(selected.created_at, selected.executed_at || selected.updated_at)}
                            </span>
                          )}
                          {selected.incident_type && (
                            <span>Tipo: <span className="font-mono text-slate-400">{selected.incident_type}</span></span>
                          )}
                        </div>
                      </div>
                    )}

                    {(selected.action_result || actionResponse?.stdout) && (
                      <div>
                        <p className="text-xs text-slate-500 mb-2 flex items-center gap-1.5">
                          <Terminal className="w-3 h-3" /> Stdout
                        </p>
                        <pre className="bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-emerald-300 font-mono overflow-x-auto whitespace-pre-wrap max-h-40 overflow-y-auto">
                          {selected.action_result || actionResponse?.stdout}
                        </pre>
                      </div>
                    )}

                    {(selected.status === 'failed' || actionResponse?.status === 'failed') && (
                      <div className="space-y-2">
                        <div className="flex items-center gap-2 text-red-400 text-sm">
                          <XCircle className="w-4 h-4" />
                          La ejecución falló — revisión manual recomendada
                        </div>
                        {(selected.action_error || actionResponse?.stderr || actionError) && (
                          <pre className="bg-slate-950 border border-red-900/40 rounded-xl p-3 text-xs text-red-300 font-mono overflow-x-auto whitespace-pre-wrap max-h-36 overflow-y-auto">
                            {selected.action_error || actionResponse?.stderr || actionError}
                          </pre>
                        )}
                      </div>
                    )}

                    {actionError && selected.status !== 'failed' && (
                      <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl px-3 py-2">
                        {actionError}
                      </p>
                    )}

                    {/* Fallback: incidente sin acción (resuelto automáticamente o solo analizado) */}
                    {!selected.proposed_action && !selected.action_result && !actionResponse && (
                      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-2">
                        <p className="text-xs text-slate-500">Resumen del incidente</p>
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          <div>
                            <p className="text-slate-600">Tipo detectado</p>
                            <p className="text-slate-300 font-mono mt-0.5">{selected.incident_type || 'No clasificado'}</p>
                          </div>
                          <div>
                            <p className="text-slate-600">Recurso afectado</p>
                            <p className="text-slate-300 font-mono mt-0.5 truncate">{selected.target || selected.container_name || '—'}</p>
                          </div>
                        </div>
                        {selected.status === 'analyzed' && (
                          <p className="text-xs text-amber-400/80 mt-2">
                            El agente analizó el incidente pero no propuso una acción ejecutable. Revisa el panel "Agente" para ver el análisis completo.
                          </p>
                        )}
                        {(selected.status === 'resolved' || selected.status === 'failed') && !selected.executed_at && (
                          <p className="text-xs text-slate-500 mt-2">
                            Resuelto automáticamente — sin acción ejecutada por el agente.
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </>
          ) : (
            <EmptyDetail hasIncidents={incidents.length > 0} onNew={() => setShowCreateModal(true)} />
          )}
        </div>

        {/* ── Col 3: Context panel (only when incident selected) ────────── */}
        {selected && (
          <div className="w-96 shrink-0 flex flex-col overflow-hidden">

            {/* Tab bar */}
            <div className="shrink-0 flex border-b border-slate-800">
              {CONTEXT_TABS.map(({ id, label, Icon }) => (
                <button
                  key={id}
                  onClick={() => setContextTab(id)}
                  className={`flex-1 flex items-center justify-center gap-1 px-1 py-3 text-xs font-medium border-b-2 transition-colors ${
                    contextTab === id
                      ? 'border-sky-500 text-sky-400'
                      : 'border-transparent text-slate-500 hover:text-slate-300'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  {label}
                </button>
              ))}
            </div>

            {/* Tab content — independently scrollable */}
            <div className="flex-1 overflow-y-auto p-5">
              {contextTab === 'agent' && (
                <AgentReasoningPanel
                  reasoning={selected.agent_reasoning}
                  status={selected.status}
                />
              )}

              {contextTab === 'metrics' && (
                <div className="space-y-5">
                  <div className="space-y-2">
                    <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Métricas del servicio</p>
                    <MetricsPanel incidentId={selected.id} metricsSnapshot={selected.metrics_snapshot} />
                  </div>
                  {selected.logs && (
                    <div className="space-y-2">
                      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Logs del contenedor</p>
                      <ColoredLogs logs={selected.logs} />
                    </div>
                  )}
                  {!selected.logs && (
                    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                      <p className="text-xs text-slate-600">Sin logs disponibles</p>
                    </div>
                  )}
                </div>
              )}

              {contextTab === 'runbooks' && (
                <div className="space-y-5">
                  <div className="space-y-2">
                    <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Runbooks relevantes</p>
                    <RunbookViewer incidentId={selected.id} />
                  </div>
                  <SimilarIncidentsCard incidentId={selected.id} />
                </div>
              )}

              {contextTab === 'history' && (
                <div className="space-y-2">
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Línea de tiempo</p>
                  <IncidentTimeline incident={selected} />
                </div>
              )}

              {contextTab === 'postmortem' && (
                <PostMortemEditor incident={selected} />
              )}
            </div>
          </div>
        )}
      </div>

      {showCreateModal && <CreateIncidentModal onClose={() => setShowCreateModal(false)} />}
      {showExportModal && selected && (
        <ExportModal incident={selected} onClose={() => setShowExportModal(false)} />
      )}
    </div>
  )
}

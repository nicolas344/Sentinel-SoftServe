import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import {
  Shield, CheckCircle2, XCircle, RefreshCw, ArrowRight,
  Activity, Database, Bell, BarChart2, BookOpen, Layers,
  ChevronRight, Cpu, GitMerge, Wrench, FlaskConical,
  TrendingUp, Clock, AlertTriangle, CheckCheck,
} from 'lucide-react'
import { supabase } from '../lib/supabase'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// ── Integration health ────────────────────────────────────────────────────────

const SERVICE_META = {
  prometheus:   { label: 'Prometheus',   Icon: BarChart2,    desc: 'Métricas de contenedores y servidores' },
  loki:         { label: 'Loki',         Icon: Activity,     desc: 'Agregación de logs' },
  chromadb:     { label: 'ChromaDB',     Icon: Database,     desc: 'Memoria semántica del agente (runbooks)' },
  alertmanager: { label: 'Alertmanager', Icon: Bell,         desc: 'Gestión y enrutamiento de alertas' },
  langfuse:     { label: 'LangFuse',     Icon: Layers,       desc: 'Observabilidad del agente IA' },
  supabase:     { label: 'Supabase',     Icon: BookOpen,     desc: 'Base de datos y autenticación' },
}

function ServiceRow({ name, info }) {
  const meta = SERVICE_META[name] || { label: name, Icon: Activity, desc: '' }
  const { label, Icon, desc } = meta
  const isOk = info?.status === 'ok'

  return (
    <div className="flex items-start gap-4 py-3.5 border-b border-slate-800 last:border-0">
      <div className={`mt-0.5 w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${isOk ? 'bg-emerald-500/10' : 'bg-red-500/10'}`}>
        <Icon className={`w-4 h-4 ${isOk ? 'text-emerald-400' : 'text-red-400'}`} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium text-slate-200">{label}</span>
          {isOk ? (
            <span className="flex items-center gap-1 text-xs text-emerald-400">
              <CheckCircle2 className="w-3 h-3" />
              Conectado
              {info.latency_ms !== undefined && <span className="text-slate-600 ml-1">{info.latency_ms}ms</span>}
            </span>
          ) : (
            <span className="flex items-center gap-1 text-xs text-red-400">
              <XCircle className="w-3 h-3" />
              {info?.error || 'Sin respuesta'}
            </span>
          )}
        </div>
        <p className="text-xs text-slate-600 mt-0.5">{desc}</p>
        {name === 'chromadb' && !isOk && (
          <div className="mt-2.5 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2.5">
            <p className="text-xs text-slate-500 mb-1.5">Comandos para iniciar ChromaDB:</p>
            <pre className="text-xs text-sky-300 font-mono leading-relaxed">
              {`docker compose up -d chromadb\npython Backend/scripts/seed_chromadb.py`}
            </pre>
          </div>
        )}
      </div>
    </div>
  )
}

function AggregateStatus({ status }) {
  const config = {
    healthy:  { Icon: CheckCircle2, color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/20', label: 'Todos los servicios operativos' },
    degraded: { Icon: Activity,     color: 'text-amber-400',   bg: 'bg-amber-500/10 border-amber-500/20',     label: 'Algunos servicios con problemas' },
    critical: { Icon: XCircle,      color: 'text-red-400',     bg: 'bg-red-500/10 border-red-500/20',         label: 'Múltiples servicios caídos' },
  }
  const c = config[status] || config.degraded
  const { Icon } = c
  return (
    <div className={`flex items-center gap-2 px-3 py-2 rounded-lg border ${c.bg} mb-4`}>
      <Icon className={`w-4 h-4 ${c.color} shrink-0`} />
      <span className={`text-sm font-medium ${c.color}`}>{c.label}</span>
    </div>
  )
}

// ── Labs configuration ─────────────────────────────────────────────────────────

const LABS = [
  {
    number: 1,
    name: 'Alert Intake',
    color: 'blue',
    Icon: Bell,
    agent: 'Supervisor',
    duration: '~5s',
    description: 'Recibe la alerta de Alertmanager y clasifica el tipo de incidente usando el LLM.',
    outputs: ['incident_type', 'status → investigating'],
    runtimes: ['Docker', 'Podman', 'Kubernetes', 'PostgreSQL'],
  },
  {
    number: 2,
    name: 'Investigation',
    color: 'purple',
    Icon: FlaskConical,
    agent: 'DomainAgent (Docker / Podman / Kubernetes / PostgreSQL)',
    duration: '~15–30s',
    description: 'El agente especializado consulta runbooks en ChromaDB, busca incidentes similares en memoria episódica y ejecuta hasta 4 herramientas read-only para recopilar evidencia.',
    outputs: ['agent_reasoning', 'tool_calls', 'status → analyzed'],
    runtimes: ['Docker', 'Podman', 'Kubernetes', 'PostgreSQL'],
  },
  {
    number: 3,
    name: 'Decision & Planning',
    color: 'amber',
    Icon: GitMerge,
    agent: 'Supervisor',
    duration: '~5s',
    description: 'El Supervisor construye la acción correctiva validándola contra la whitelist de comandos seguros y los guardrails deterministas.',
    outputs: ['proposed_action', 'status → awaiting_approval'],
    runtimes: ['Docker', 'Podman', 'Kubernetes', 'PostgreSQL'],
  },
  {
    number: 4,
    name: 'Action & Verification',
    color: 'indigo',
    Icon: Wrench,
    agent: 'verification.py',
    duration: '~10–20s',
    description: 'Tras la aprobación del ingeniero, ejecuta el comando propuesto y verifica el resultado inspeccionando el recurso afectado.',
    outputs: ['action_result', 'executed_at', 'status → resolved / failed'],
    runtimes: ['Docker', 'Podman', 'Kubernetes', 'PostgreSQL'],
  },
  {
    number: 5,
    name: 'Post-Incident',
    color: 'emerald',
    Icon: BookOpen,
    agent: 'postmortem service',
    duration: '~5s',
    description: 'Genera el post-mortem en markdown, guarda el incidente en memoria episódica de ChromaDB y cierra el ciclo de vida.',
    outputs: ['post-mortem exportable', 'memoria episódica actualizada'],
    runtimes: ['Todos'],
  },
]

const LAB_COLORS = {
  blue:    { dot: 'bg-blue-400',    badge: 'bg-blue-500/10 text-blue-300 border-blue-500/20',    num: 'bg-blue-500/20 text-blue-300' },
  purple:  { dot: 'bg-purple-400',  badge: 'bg-purple-500/10 text-purple-300 border-purple-500/20',  num: 'bg-purple-500/20 text-purple-300' },
  amber:   { dot: 'bg-amber-400',   badge: 'bg-amber-500/10 text-amber-300 border-amber-500/20',   num: 'bg-amber-500/20 text-amber-300' },
  indigo:  { dot: 'bg-indigo-400',  badge: 'bg-indigo-500/10 text-indigo-300 border-indigo-500/20',  num: 'bg-indigo-500/20 text-indigo-300' },
  emerald: { dot: 'bg-emerald-400', badge: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20', num: 'bg-emerald-500/20 text-emerald-300' },
}

function LabCard({ lab, isLast }) {
  const c = LAB_COLORS[lab.color]
  const { Icon } = lab
  return (
    <div className="flex gap-4">
      <div className="flex flex-col items-center">
        <div className={`w-8 h-8 rounded-full ${c.num} flex items-center justify-center text-xs font-bold shrink-0`}>
          {lab.number}
        </div>
        {!isLast && <div className="w-px flex-1 bg-slate-800 mt-2" />}
      </div>
      <div className={`pb-6 flex-1 ${isLast ? 'pb-0' : ''}`}>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
          <div className="flex items-start gap-3">
            <div className={`w-8 h-8 rounded-lg bg-slate-800 flex items-center justify-center shrink-0`}>
              <Icon className={`w-4 h-4 ${c.dot.replace('bg-', 'text-').replace('-400', '-400')}`} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-semibold text-slate-100">Lab {lab.number} — {lab.name}</span>
                <span className="text-[10px] text-slate-600 font-mono">{lab.duration}</span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">{lab.agent}</p>
            </div>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">{lab.description}</p>
          <div className="flex flex-wrap gap-1.5">
            {lab.outputs.map(o => (
              <span key={o} className={`text-[10px] px-2 py-0.5 rounded-full border font-mono ${c.badge}`}>{o}</span>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

// ── System metrics ─────────────────────────────────────────────────────────────

function computeMetrics(incidents) {
  const total = incidents.length
  if (total === 0) return null

  const resolved = incidents.filter(i => i.status === 'resolved').length
  const failed   = incidents.filter(i => i.status === 'failed').length
  const active   = incidents.filter(i => !['resolved', 'failed'].includes(i.status)).length

  const mttrMs = incidents
    .filter(i => i.status === 'resolved' && i.created_at && i.executed_at)
    .map(i => new Date(i.executed_at) - new Date(i.created_at))
    .filter(ms => ms > 0)

  const avgMttr = mttrMs.length > 0
    ? Math.round(mttrMs.reduce((a, b) => a + b, 0) / mttrMs.length / 1000)
    : null

  const formatMttr = (secs) => {
    if (secs === null) return '—'
    if (secs < 60) return `${secs}s`
    const m = Math.floor(secs / 60), s = secs % 60
    return `${m}m ${s}s`
  }

  const bySeverity = { critical: 0, high: 0, medium: 0, low: 0 }
  incidents.forEach(i => { if (i.severity in bySeverity) bySeverity[i.severity]++ })

  const byType = {}
  incidents.forEach(i => {
    const t = i.incident_type || 'unknown'
    byType[t] = (byType[t] || 0) + 1
  })
  const topType = Object.entries(byType).sort((a, b) => b[1] - a[1])[0]

  return { total, resolved, failed, active, avgMttr: formatMttr(avgMttr), bySeverity, topType }
}

const SEVERITY_COLORS = {
  critical: 'bg-red-500',
  high:     'bg-orange-500',
  medium:   'bg-yellow-500',
  low:      'bg-green-500',
}

function MetricCard({ Icon, label, value, sub, iconColor }) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-2">
        <Icon className={`w-3.5 h-3.5 ${iconColor}`} />
        <span className="text-[10px] text-slate-500 uppercase tracking-wider">{label}</span>
      </div>
      <p className="text-2xl font-bold text-slate-100 font-mono">{value}</p>
      {sub && <p className="text-[11px] text-slate-600 mt-1">{sub}</p>}
    </div>
  )
}

function SystemMetrics() {
  const [metrics, setMetrics] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const { data: { session } } = await supabase.auth.getSession()
        const token = session?.access_token
        const res = await fetch(`${API_URL}/api/incidents?limit=200`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (!res.ok) throw new Error()
        const data = await res.json()
        const list = Array.isArray(data) ? data : (data.data || [])
        if (!cancelled) setMetrics(computeMetrics(list))
      } catch {
        if (!cancelled) setMetrics(null)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [])

  if (loading) {
    return (
      <div className="py-10 flex items-center justify-center gap-2 text-slate-600 text-sm">
        <RefreshCw className="w-4 h-4 animate-spin" />
        Calculando métricas…
      </div>
    )
  }

  if (!metrics) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 text-center">
        <p className="text-sm text-slate-600">No hay datos de incidentes disponibles.</p>
      </div>
    )
  }

  const resolutionRate = metrics.total > 0
    ? Math.round((metrics.resolved / metrics.total) * 100)
    : 0

  return (
    <div className="space-y-4">
      {/* KPI grid */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <MetricCard Icon={BarChart2}    label="Total incidentes"  value={metrics.total}        iconColor="text-sky-400" />
        <MetricCard Icon={CheckCheck}   label="Resueltos"         value={metrics.resolved}      sub={`${resolutionRate}% tasa de resolución`} iconColor="text-emerald-400" />
        <MetricCard Icon={Clock}        label="MTTR promedio"     value={metrics.avgMttr}       sub="tiempo hasta ejecución" iconColor="text-amber-400" />
        <MetricCard Icon={AlertTriangle} label="Activos ahora"    value={metrics.active}        sub={`${metrics.failed} fallaron`} iconColor="text-orange-400" />
      </div>

      {/* Severity breakdown */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
        <p className="text-xs text-slate-500 uppercase tracking-wider mb-3">Incidentes por severidad</p>
        <div className="space-y-2">
          {Object.entries(metrics.bySeverity).map(([sev, count]) => {
            const pct = metrics.total > 0 ? Math.round((count / metrics.total) * 100) : 0
            return (
              <div key={sev} className="flex items-center gap-3">
                <span className="text-xs text-slate-400 w-16 capitalize">{sev}</span>
                <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                  <div className={`h-full rounded-full ${SEVERITY_COLORS[sev]}`} style={{ width: `${pct}%` }} />
                </div>
                <span className="text-xs font-mono text-slate-500 w-8 text-right">{count}</span>
              </div>
            )
          })}
        </div>
      </div>

      {/* Top incident type */}
      {metrics.topType && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex items-center gap-4">
          <TrendingUp className="w-5 h-5 text-sky-400 shrink-0" />
          <div>
            <p className="text-xs text-slate-500 uppercase tracking-wider">Tipo más frecuente</p>
            <p className="text-sm font-semibold text-slate-100 mt-0.5 font-mono">
              {metrics.topType[0]}
              <span className="text-slate-600 font-normal ml-2">({metrics.topType[1]} incidentes)</span>
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function Setup() {
  const [health, setHealth]           = useState(null)
  const [loading, setLoading]         = useState(true)
  const [lastUpdated, setLastUpdated] = useState(null)

  const fetchHealth = useCallback(async () => {
    setLoading(true)
    try {
      const res  = await fetch(`${API_URL}/api/health`, { signal: AbortSignal.timeout(8000) })
      const data = await res.json()
      setHealth(data)
      setLastUpdated(new Date())
    } catch {
      setHealth(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchHealth()
    const timer = window.setInterval(fetchHealth, 30000)
    return () => window.clearInterval(timer)
  }, [fetchHealth])

  const services = health?.services ? Object.entries(health.services) : []

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50 flex flex-col">

      {/* Header */}
      <header className="flex items-center justify-between px-8 py-4 border-b border-slate-800 shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-sky-600/20 border border-sky-500/30 flex items-center justify-center">
            <Shield className="w-4 h-4 text-sky-400" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-slate-100">Sentinel</h1>
            <p className="text-xs text-slate-500">Configuración del sistema</p>
          </div>
        </div>
        <Link
          to="/"
          className="flex items-center gap-1.5 text-sm text-slate-400 border border-slate-700 rounded-lg px-3.5 py-1.5 hover:border-slate-500 hover:text-slate-300 transition-colors"
        >
          Ir al Dashboard <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </header>

      <div className="flex-1 max-w-2xl mx-auto w-full px-6 py-10 space-y-10">

        {/* What is Sentinel */}
        <div>
          <h2 className="text-base font-semibold text-slate-100 mb-4">¿Qué es Sentinel?</h2>
          <div className="grid gap-3">
            {[
              { Icon: Bell,         color: 'text-red-400',     bg: 'bg-red-500/10',     title: 'Detección',   body: 'Recibe alertas de Prometheus y Alertmanager en tiempo real.' },
              { Icon: Activity,     color: 'text-sky-400',     bg: 'bg-sky-500/10',     title: 'Análisis',    body: 'Un agente IA investiga, diagnostica y propone la solución óptima.' },
              { Icon: CheckCircle2, color: 'text-emerald-400', bg: 'bg-emerald-500/10', title: 'Resolución',  body: 'Tú apruebas la acción con un clic — Sentinel ejecuta y verifica.' },
            ].map(({ Icon, color, bg, title, body }) => (
              <div key={title} className="flex items-start gap-3 bg-slate-900 border border-slate-800 rounded-xl p-4">
                <div className={`w-8 h-8 rounded-lg ${bg} flex items-center justify-center shrink-0`}>
                  <Icon className={`w-4 h-4 ${color}`} />
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-200">{title}</p>
                  <p className="text-xs text-slate-500 mt-0.5">{body}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Labs configuration — US-20 */}
        <div>
          <div className="flex items-center gap-2 mb-4">
            <Cpu className="w-4 h-4 text-slate-500" />
            <h2 className="text-base font-semibold text-slate-100">Arquitectura de Labs del agente</h2>
          </div>
          <p className="text-xs text-slate-500 mb-5">
            Cada incidente pasa por 5 Labs en secuencia. El agente especializado se activa en el Lab 2 según el runtime detectado.
          </p>
          <div>
            {LABS.map((lab, i) => (
              <LabCard key={lab.number} lab={lab} isLast={i === LABS.length - 1} />
            ))}
          </div>
        </div>

        {/* Integration health — US-18 */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-slate-100">Estado de integraciones</h2>
            <div className="flex items-center gap-3">
              {lastUpdated && (
                <span className="text-xs text-slate-600">
                  {lastUpdated.toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </span>
              )}
              <button
                onClick={fetchHealth}
                disabled={loading}
                className="flex items-center gap-1.5 text-xs border border-slate-700 rounded-lg px-3 py-1.5 text-slate-400 hover:border-slate-500 hover:text-slate-300 transition-colors disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                {loading ? 'Actualizando…' : 'Actualizar'}
              </button>
            </div>
          </div>

          {health && <AggregateStatus status={health.status} />}

          <div className="bg-slate-900 border border-slate-800 rounded-xl px-5">
            {loading && services.length === 0 ? (
              <div className="py-8 flex items-center justify-center gap-2 text-slate-600 text-sm">
                <RefreshCw className="w-4 h-4 animate-spin" />
                Comprobando servicios…
              </div>
            ) : services.length > 0 ? (
              services.map(([name, info]) => (
                <ServiceRow key={name} name={name} info={info} />
              ))
            ) : (
              <div className="py-8 flex flex-col items-center gap-2 text-red-400 text-sm">
                <XCircle className="w-5 h-5" />
                No se pudo conectar al backend ({API_URL})
              </div>
            )}
          </div>
        </div>

        {/* System metrics — US-17 */}
        <div>
          <div className="flex items-center gap-2 mb-4">
            <BarChart2 className="w-4 h-4 text-slate-500" />
            <h2 className="text-base font-semibold text-slate-100">Métricas del sistema</h2>
          </div>
          <SystemMetrics />
        </div>

        {/* First-time guide */}
        <div>
          <h2 className="text-base font-semibold text-slate-100 mb-4">Guía de primer uso</h2>
          <ol className="space-y-3">
            {[
              { cmd: 'docker compose up -d',                        desc: 'Levanta el stack completo' },
              { cmd: null,                                           desc: 'Verifica que todos los indicadores de arriba sean verdes' },
              { cmd: 'python Backend/scripts/seed_chromadb.py',     desc: 'Carga los runbooks en ChromaDB (solo la primera vez)' },
              { cmd: null,                                           desc: 'Vuelve al Dashboard — Sentinel monitoreará automáticamente' },
            ].map((step, i) => (
              <li key={i} className="flex gap-3 bg-slate-900 border border-slate-800 rounded-xl p-4">
                <span className="w-6 h-6 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-xs text-slate-500 font-mono shrink-0 mt-0.5">
                  {i + 1}
                </span>
                <div className="space-y-2 flex-1">
                  <p className="text-sm text-slate-300">{step.desc}</p>
                  {step.cmd && (
                    <pre className="text-xs text-sky-300 font-mono bg-slate-950 border border-slate-800 rounded-lg px-3 py-2">
                      $ {step.cmd}
                    </pre>
                  )}
                </div>
              </li>
            ))}
          </ol>
        </div>

        <Link
          to="/"
          className="inline-flex items-center gap-2 bg-sky-600 hover:bg-sky-500 text-white rounded-xl px-5 py-3 text-sm font-semibold transition-colors"
        >
          Ir al Dashboard <ChevronRight className="w-4 h-4" />
        </Link>
      </div>
    </div>
  )
}

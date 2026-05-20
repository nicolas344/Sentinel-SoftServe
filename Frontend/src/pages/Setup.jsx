import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import {
  Shield, CheckCircle2, XCircle, RefreshCw, ArrowRight,
  Activity, Database, Bell, BarChart2, BookOpen, Layers,
  ChevronRight, Cpu, GitMerge, Wrench, FlaskConical,
  TrendingUp, Clock, AlertTriangle, CheckCheck, Info,
} from 'lucide-react'
import { supabase } from '../lib/supabase'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// ── Integration health ────────────────────────────────────────────────────────

const SERVICE_META = {
  prometheus:   { label: 'Prometheus',   Icon: BarChart2,  desc: 'Métricas de contenedores' },
  loki:         { label: 'Loki',         Icon: Activity,   desc: 'Agregación de logs' },
  chromadb:     { label: 'ChromaDB',     Icon: Database,   desc: 'Memoria semántica del agente' },
  alertmanager: { label: 'Alertmanager', Icon: Bell,       desc: 'Enrutamiento de alertas' },
  langfuse:     { label: 'LangFuse',     Icon: Layers,     desc: 'Observabilidad del agente IA' },
  supabase:     { label: 'Supabase',     Icon: BookOpen,   desc: 'Base de datos y auth' },
}

function ServiceRow({ name, info }) {
  const meta = SERVICE_META[name] || { label: name, Icon: Activity, desc: '' }
  const { label, Icon, desc } = meta
  const isOk = info?.status === 'ok'
  return (
    <div className="flex items-center gap-4 py-3 border-b border-slate-800 last:border-0">
      <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${isOk ? 'bg-emerald-500/10' : 'bg-red-500/10'}`}>
        <Icon className={`w-4 h-4 ${isOk ? 'text-emerald-400' : 'text-red-400'}`} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-slate-200">{label}</span>
          {isOk ? (
            <span className="flex items-center gap-1 text-xs text-emerald-400">
              <CheckCircle2 className="w-3 h-3" /> Conectado
              {info.latency_ms !== undefined && <span className="text-slate-600 ml-1">{info.latency_ms}ms</span>}
            </span>
          ) : (
            <span className="flex items-center gap-1 text-xs text-red-400">
              <XCircle className="w-3 h-3" /> {info?.error || 'Sin respuesta'}
            </span>
          )}
        </div>
        <p className="text-xs text-slate-600">{desc}</p>
      </div>
      {name === 'chromadb' && !isOk && (
        <div className="shrink-0 text-right">
          <p className="text-[10px] text-slate-600 font-mono">docker compose up -d chromadb</p>
        </div>
      )}
    </div>
  )
}

// ── Labs ──────────────────────────────────────────────────────────────────────

const LABS = [
  {
    number: 1, name: 'Alert Intake', color: 'blue', Icon: Bell,
    agent: 'Supervisor', duration: '~5s',
    description: 'Recibe la alerta y clasifica el tipo de incidente con el LLM.',
    outputs: ['incident_type', 'status → investigating'],
  },
  {
    number: 2, name: 'Investigation', color: 'purple', Icon: FlaskConical,
    agent: 'DomainAgent (Docker / Podman / Kubernetes / PostgreSQL)', duration: '~15–30s',
    description: 'El agente especializado consulta runbooks en ChromaDB, memoria episódica, y ejecuta hasta 4 herramientas read-only.',
    outputs: ['agent_reasoning', 'tool_calls', 'status → analyzed'],
  },
  {
    number: 3, name: 'Decision & Planning', color: 'amber', Icon: GitMerge,
    agent: 'Supervisor', duration: '~5s',
    description: 'Construye la acción correctiva y la valida contra la whitelist de comandos seguros y los guardrails.',
    outputs: ['proposed_action', 'status → awaiting_approval'],
  },
  {
    number: 4, name: 'Action & Verification', color: 'indigo', Icon: Wrench,
    agent: 'verification.py', duration: '~10–20s',
    description: 'Ejecuta el comando aprobado por el ingeniero y verifica el resultado inspeccionando el recurso.',
    outputs: ['action_result', 'executed_at', 'status → resolved / failed'],
  },
  {
    number: 5, name: 'Post-Incident', color: 'emerald', Icon: BookOpen,
    agent: 'postmortem service', duration: '~5s',
    description: 'Genera el post-mortem en markdown y guarda el incidente en memoria episódica de ChromaDB.',
    outputs: ['post-mortem exportable', 'memoria episódica actualizada'],
  },
]

const LAB_COLORS = {
  blue:    { num: 'bg-blue-500/20 text-blue-300',    badge: 'bg-blue-500/10 text-blue-300 border-blue-500/20',    icon: 'text-blue-400',    line: 'bg-blue-500/20' },
  purple:  { num: 'bg-purple-500/20 text-purple-300', badge: 'bg-purple-500/10 text-purple-300 border-purple-500/20', icon: 'text-purple-400',  line: 'bg-purple-500/20' },
  amber:   { num: 'bg-amber-500/20 text-amber-300',   badge: 'bg-amber-500/10 text-amber-300 border-amber-500/20',   icon: 'text-amber-400',   line: 'bg-amber-500/20' },
  indigo:  { num: 'bg-indigo-500/20 text-indigo-300', badge: 'bg-indigo-500/10 text-indigo-300 border-indigo-500/20', icon: 'text-indigo-400', line: 'bg-indigo-500/20' },
  emerald: { num: 'bg-emerald-500/20 text-emerald-300', badge: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20', icon: 'text-emerald-400', line: 'bg-emerald-500/20' },
}

function LabRow({ lab, isLast }) {
  const c = LAB_COLORS[lab.color]
  const { Icon } = lab
  return (
    <div className="flex gap-4">
      <div className="flex flex-col items-center">
        <div className={`w-7 h-7 rounded-full ${c.num} flex items-center justify-center text-xs font-bold shrink-0`}>
          {lab.number}
        </div>
        {!isLast && <div className={`w-px flex-1 mt-1 ${c.line}`} style={{ minHeight: 16 }} />}
      </div>
      <div className={`flex-1 pb-4 ${isLast ? 'pb-0' : ''}`}>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-3.5 space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            <Icon className={`w-3.5 h-3.5 ${c.icon} shrink-0`} />
            <span className="text-sm font-semibold text-slate-100">Lab {lab.number} — {lab.name}</span>
            <span className="text-[10px] text-slate-600 font-mono">{lab.duration}</span>
            <span className="text-[10px] text-slate-500 ml-auto">{lab.agent}</span>
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

// ── System metrics ────────────────────────────────────────────────────────────

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
  const avgMttrSec = mttrMs.length > 0
    ? Math.round(mttrMs.reduce((a, b) => a + b, 0) / mttrMs.length / 1000) : null
  const fmt = s => s === null ? '—' : s < 60 ? `${s}s` : `${Math.floor(s/60)}m ${s%60}s`
  const bySeverity = { critical: 0, high: 0, medium: 0, low: 0 }
  incidents.forEach(i => { if (i.severity in bySeverity) bySeverity[i.severity]++ })
  const byType = {}
  incidents.forEach(i => { const t = i.incident_type || 'unknown'; byType[t] = (byType[t] || 0) + 1 })
  const topType = Object.entries(byType).sort((a, b) => b[1] - a[1])[0]
  return { total, resolved, failed, active, avgMttr: fmt(avgMttrSec), bySeverity, topType, resolutionRate: Math.round((resolved / total) * 100) }
}

const SEVERITY_COLORS = { critical: 'bg-red-500', high: 'bg-orange-500', medium: 'bg-yellow-500', low: 'bg-green-500' }

function SystemMetricsTab() {
  const [metrics, setMetrics] = useState(null)
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const { data: { session } } = await supabase.auth.getSession()
        const res = await fetch(`${API_URL}/api/incidents?limit=200`, {
          headers: { Authorization: `Bearer ${session?.access_token}` },
        })
        if (!res.ok) throw new Error()
        const data = await res.json()
        const list = Array.isArray(data) ? data : (data.data || [])
        if (!cancelled) setMetrics(computeMetrics(list))
      } catch { if (!cancelled) setMetrics(null) }
      finally { if (!cancelled) setLoading(false) }
    }
    load()
    return () => { cancelled = true }
  }, [])

  if (loading) return (
    <div className="flex items-center justify-center gap-2 text-slate-600 text-sm py-16">
      <RefreshCw className="w-4 h-4 animate-spin" /> Calculando métricas…
    </div>
  )
  if (!metrics) return (
    <div className="text-center py-16 text-sm text-slate-600">No hay incidentes registrados aún.</div>
  )
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          { Icon: BarChart2,     label: 'Total incidentes',  value: metrics.total,            color: 'text-sky-400',     sub: 'procesados' },
          { Icon: CheckCheck,    label: 'Resueltos',         value: metrics.resolved,          color: 'text-emerald-400', sub: `${metrics.resolutionRate}% tasa de resolución` },
          { Icon: Clock,         label: 'MTTR promedio',     value: metrics.avgMttr,           color: 'text-amber-400',   sub: 'hasta ejecución' },
          { Icon: AlertTriangle, label: 'Activos ahora',     value: metrics.active,            color: 'text-orange-400',  sub: `${metrics.failed} fallaron` },
        ].map(({ Icon, label, value, color, sub }) => (
          <div key={label} className="bg-slate-900 border border-slate-800 rounded-xl p-4">
            <div className="flex items-center gap-1.5 mb-2">
              <Icon className={`w-3.5 h-3.5 ${color}`} />
              <span className="text-[10px] text-slate-500 uppercase tracking-wider">{label}</span>
            </div>
            <p className="text-2xl font-bold text-slate-100 font-mono">{value}</p>
            <p className="text-[11px] text-slate-600 mt-1">{sub}</p>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <p className="text-xs text-slate-500 uppercase tracking-wider mb-3">Por severidad</p>
          <div className="space-y-2.5">
            {Object.entries(metrics.bySeverity).map(([sev, count]) => {
              const pct = metrics.total > 0 ? Math.round((count / metrics.total) * 100) : 0
              return (
                <div key={sev} className="flex items-center gap-3">
                  <span className="text-xs text-slate-400 w-16 capitalize">{sev}</span>
                  <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                    <div className={`h-full rounded-full ${SEVERITY_COLORS[sev]}`} style={{ width: `${pct}%` }} />
                  </div>
                  <span className="text-xs font-mono text-slate-500 w-6 text-right">{count}</span>
                </div>
              )
            })}
          </div>
        </div>
        {metrics.topType && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex items-center gap-4">
            <TrendingUp className="w-6 h-6 text-sky-400 shrink-0" />
            <div>
              <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">Tipo más frecuente</p>
              <p className="text-lg font-bold text-slate-100 font-mono">{metrics.topType[0]}</p>
              <p className="text-xs text-slate-600 mt-0.5">{metrics.topType[1]} incidentes registrados</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────────

const TABS = [
  { id: 'integrations', label: 'Integraciones',    Icon: Activity },
  { id: 'labs',         label: 'Labs del Agente',  Icon: Cpu },
  { id: 'metrics',      label: 'Métricas',         Icon: BarChart2 },
  { id: 'guide',        label: 'Guía de inicio',   Icon: Info },
]

export default function Setup() {
  const [activeTab, setActiveTab]     = useState('integrations')
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
    } catch { setHealth(null) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => {
    fetchHealth()
    const timer = window.setInterval(fetchHealth, 30000)
    return () => window.clearInterval(timer)
  }, [fetchHealth])

  const services    = health?.services ? Object.entries(health.services) : []
  const errorCount  = services.filter(([, v]) => v?.status !== 'ok').length
  const statusColor = !health ? 'text-slate-500' : errorCount === 0 ? 'text-emerald-400' : errorCount <= 2 ? 'text-amber-400' : 'text-red-400'
  const statusLabel = !health ? 'Comprobando…' : errorCount === 0 ? 'Todos los servicios operativos' : `${errorCount} servicio${errorCount > 1 ? 's' : ''} con problemas`

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

        {/* Aggregate status pill */}
        <div className="hidden sm:flex items-center gap-2">
          {loading
            ? <RefreshCw className="w-3.5 h-3.5 text-slate-600 animate-spin" />
            : <span className={`w-2 h-2 rounded-full ${errorCount === 0 ? 'bg-emerald-400' : errorCount <= 2 ? 'bg-amber-400' : 'bg-red-400'} ${errorCount === 0 ? '' : 'animate-pulse'}`} />
          }
          <span className={`text-xs font-medium ${statusColor}`}>{statusLabel}</span>
          {lastUpdated && (
            <span className="text-[10px] text-slate-700 ml-2">
              {lastUpdated.toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </span>
          )}
          <button
            onClick={fetchHealth}
            disabled={loading}
            className="ml-2 flex items-center gap-1 text-[11px] border border-slate-800 rounded-lg px-2 py-1 text-slate-500 hover:border-slate-600 hover:text-slate-400 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
            Actualizar
          </button>
        </div>

        <Link
          to="/"
          className="flex items-center gap-1.5 text-sm text-slate-400 border border-slate-700 rounded-lg px-3.5 py-1.5 hover:border-slate-500 hover:text-slate-300 transition-colors"
        >
          Dashboard <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </header>

      {/* Tab navigation */}
      <div className="border-b border-slate-800 px-8 shrink-0">
        <div className="flex gap-1">
          {TABS.map(({ id, label, Icon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === id
                  ? 'border-sky-500 text-sky-400'
                  : 'border-transparent text-slate-500 hover:text-slate-300 hover:border-slate-700'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {label}
              {id === 'integrations' && errorCount > 0 && !loading && (
                <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse" />
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-8 py-8">

          {/* ── Integraciones ─────────────────────────────────────────────── */}
          {activeTab === 'integrations' && (
            <div className="space-y-4">
              <div>
                <h2 className="text-base font-semibold text-slate-100 mb-1">Estado de integraciones</h2>
                <p className="text-xs text-slate-500">Se actualiza automáticamente cada 30 segundos.</p>
              </div>

              {health && (
                <div className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm font-medium ${
                  errorCount === 0
                    ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                    : errorCount <= 2
                      ? 'bg-amber-500/10 border-amber-500/20 text-amber-400'
                      : 'bg-red-500/10 border-red-500/20 text-red-400'
                }`}>
                  {errorCount === 0
                    ? <CheckCircle2 className="w-4 h-4 shrink-0" />
                    : <AlertTriangle className="w-4 h-4 shrink-0" />
                  }
                  {statusLabel}
                </div>
              )}

              <div className="bg-slate-900 border border-slate-800 rounded-xl px-5">
                {loading && services.length === 0 ? (
                  <div className="py-10 flex items-center justify-center gap-2 text-slate-600 text-sm">
                    <RefreshCw className="w-4 h-4 animate-spin" /> Comprobando servicios…
                  </div>
                ) : services.length > 0 ? (
                  services.map(([name, info]) => <ServiceRow key={name} name={name} info={info} />)
                ) : (
                  <div className="py-10 flex flex-col items-center gap-2 text-red-400 text-sm">
                    <XCircle className="w-5 h-5" />
                    No se pudo conectar al backend ({API_URL})
                  </div>
                )}
              </div>

              <div>
                <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">¿Qué es Sentinel?</h3>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { Icon: Bell,         color: 'text-red-400',     bg: 'bg-red-500/10',     title: 'Detección',  body: 'Recibe alertas de Prometheus en tiempo real.' },
                    { Icon: Activity,     color: 'text-sky-400',     bg: 'bg-sky-500/10',     title: 'Análisis',   body: 'El agente IA investiga y propone la solución.' },
                    { Icon: CheckCircle2, color: 'text-emerald-400', bg: 'bg-emerald-500/10', title: 'Resolución', body: 'Tú apruebas — Sentinel ejecuta y verifica.' },
                  ].map(({ Icon, color, bg, title, body }) => (
                    <div key={title} className="flex flex-col gap-2 bg-slate-900 border border-slate-800 rounded-xl p-3">
                      <div className={`w-7 h-7 rounded-lg ${bg} flex items-center justify-center`}>
                        <Icon className={`w-3.5 h-3.5 ${color}`} />
                      </div>
                      <p className="text-xs font-semibold text-slate-200">{title}</p>
                      <p className="text-[11px] text-slate-500 leading-relaxed">{body}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* ── Labs ──────────────────────────────────────────────────────── */}
          {activeTab === 'labs' && (
            <div className="space-y-4">
              <div>
                <h2 className="text-base font-semibold text-slate-100 mb-1">Arquitectura de Labs del agente</h2>
                <p className="text-xs text-slate-500">Cada incidente pasa por 5 Labs en secuencia. El agente especializado se activa en el Lab 2 según el runtime detectado.</p>
              </div>
              <div>
                {LABS.map((lab, i) => <LabRow key={lab.number} lab={lab} isLast={i === LABS.length - 1} />)}
              </div>
            </div>
          )}

          {/* ── Métricas ──────────────────────────────────────────────────── */}
          {activeTab === 'metrics' && (
            <div className="space-y-4">
              <div>
                <h2 className="text-base font-semibold text-slate-100 mb-1">Métricas del sistema</h2>
                <p className="text-xs text-slate-500">Calculado sobre los últimos 200 incidentes registrados.</p>
              </div>
              <SystemMetricsTab />
            </div>
          )}

          {/* ── Guía ──────────────────────────────────────────────────────── */}
          {activeTab === 'guide' && (
            <div className="space-y-4">
              <div>
                <h2 className="text-base font-semibold text-slate-100 mb-1">Guía de primer uso</h2>
                <p className="text-xs text-slate-500">Sigue estos pasos para poner Sentinel en funcionamiento.</p>
              </div>
              <ol className="space-y-3">
                {[
                  { cmd: 'docker compose up -d',                    desc: 'Levanta el stack completo de Sentinel' },
                  { cmd: null,                                        desc: 'Verifica que todos los indicadores en la tab Integraciones estén verdes' },
                  { cmd: 'python Backend/scripts/seed_chromadb.py', desc: 'Carga los runbooks Docker en ChromaDB (solo la primera vez)' },
                  { cmd: null,                                        desc: 'Ve al Dashboard — Sentinel detectará incidentes automáticamente vía Prometheus' },
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
              <Link
                to="/"
                className="inline-flex items-center gap-2 bg-sky-600 hover:bg-sky-500 text-white rounded-xl px-5 py-3 text-sm font-semibold transition-colors"
              >
                Ir al Dashboard <ChevronRight className="w-4 h-4" />
              </Link>
            </div>
          )}

        </div>
      </div>
    </div>
  )
}

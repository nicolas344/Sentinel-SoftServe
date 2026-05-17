import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import {
  Shield, CheckCircle2, XCircle, RefreshCw, ArrowRight,
  Activity, Database, Bell, BarChart2, BookOpen, Layers,
  ChevronRight,
} from 'lucide-react'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

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
    degraded: { Icon: Activity,     color: 'text-amber-400',   bg: 'bg-amber-500/10 border-amber-500/20',   label: 'Algunos servicios con problemas' },
    critical: { Icon: XCircle,      color: 'text-red-400',     bg: 'bg-red-500/10 border-red-500/20',       label: 'Múltiples servicios caídos' },
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

        {/* Integration health */}
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

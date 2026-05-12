import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const SERVICE_LABELS = {
  prometheus:   'Prometheus',
  loki:         'Loki',
  chromadb:     'ChromaDB',
  alertmanager: 'Alertmanager',
  langfuse:     'LangFuse',
  supabase:     'Supabase',
}

function StatusDot({ status }) {
  if (status === 'ok') {
    return <span className="w-2 h-2 rounded-full bg-emerald-400 shrink-0" />
  }
  return <span className="w-2 h-2 rounded-full bg-red-500 shrink-0" />
}

function ServiceRow({ name, info }) {
  const label = SERVICE_LABELS[name] || name
  const isOk = info?.status === 'ok'
  return (
    <div className="flex items-start gap-3 py-3 border-b border-slate-800 last:border-0">
      <StatusDot status={info?.status} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-sm font-medium text-slate-200">{label}</span>
          {isOk ? (
            <span className="text-xs text-emerald-400">
              Conectado
              {info.latency_ms !== undefined && ` · ${info.latency_ms}ms`}
              {info.url && ` · ${new URL(info.url).host}`}
            </span>
          ) : (
            <span className="text-xs text-red-400">
              Error — {info?.error || 'Sin respuesta'}
            </span>
          )}
        </div>
        {name === 'chromadb' && !isOk && (
          <div className="mt-2 bg-slate-900 border border-slate-700 rounded-md px-3 py-2">
            <p className="text-xs text-slate-400 mb-1">Para iniciar ChromaDB y cargar los runbooks:</p>
            <pre className="text-xs text-sky-300 font-mono">
              docker compose up -d chromadb{'\n'}
              python Backend/scripts/seed_chromadb.py
            </pre>
          </div>
        )}
      </div>
    </div>
  )
}

function AggregateStatus({ status }) {
  const config = {
    healthy:  { dot: 'bg-emerald-400', label: 'Todos los servicios operativos', text: 'text-emerald-400' },
    degraded: { dot: 'bg-amber-400',   label: 'Algunos servicios con problemas', text: 'text-amber-400' },
    critical: { dot: 'bg-red-500',     label: 'Múltiples servicios caídos', text: 'text-red-400' },
  }
  const c = config[status] || config.degraded
  return (
    <div className="flex items-center gap-2">
      <span className={`w-2 h-2 rounded-full ${c.dot}`} />
      <span className={`text-sm font-medium ${c.text}`}>{c.label}</span>
    </div>
  )
}

export default function Setup() {
  const [health, setHealth] = useState(null)
  const [loading, setLoading] = useState(true)
  const [lastUpdated, setLastUpdated] = useState(null)

  const fetchHealth = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_URL}/api/health`, { signal: AbortSignal.timeout(8000) })
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
      <header className="flex items-center justify-between px-8 py-4 border-b border-slate-800 shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-bold">Sentinel</h1>
          <span className="text-slate-600 text-xs font-medium tracking-widest uppercase">
            Configuración del sistema
          </span>
        </div>
        <Link
          to="/"
          className="text-sm text-slate-400 border border-slate-700 rounded-md px-3.5 py-1.5 hover:border-slate-500 hover:text-slate-300 transition-colors"
        >
          Ir al Dashboard →
        </Link>
      </header>

      <div className="flex-1 max-w-2xl mx-auto w-full px-6 py-10 space-y-8">

        {/* What is Sentinel */}
        <div>
          <h2 className="text-base font-semibold text-slate-100 mb-3">¿Qué es Sentinel?</h2>
          <ul className="space-y-2">
            {[
              'Detecta alertas de infraestructura (Prometheus / Alertmanager) en tiempo real.',
              'Un agente especializado investiga, clasifica y propone la solución óptima.',
              'Tú apruebas la acción — Sentinel la ejecuta y verifica que el servicio se recuperó.',
            ].map((item, i) => (
              <li key={i} className="flex gap-3 text-sm text-slate-300">
                <span className="text-slate-600 shrink-0 font-mono">{i + 1}.</span>
                {item}
              </li>
            ))}
          </ul>
        </div>

        {/* Integration health */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-base font-semibold text-slate-100">Estado de integraciones</h2>
            <div className="flex items-center gap-3">
              {lastUpdated && (
                <span className="text-xs text-slate-600">
                  Actualizado {lastUpdated.toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </span>
              )}
              <button
                onClick={fetchHealth}
                disabled={loading}
                className="text-xs border border-slate-700 rounded-md px-3 py-1.5 text-slate-400 hover:border-slate-500 hover:text-slate-300 transition-colors disabled:opacity-50"
              >
                {loading ? 'Actualizando…' : 'Actualizar'}
              </button>
            </div>
          </div>

          {health && <AggregateStatus status={health.status} />}

          <div className="mt-3 bg-slate-900 border border-slate-800 rounded-lg px-4">
            {loading && services.length === 0 ? (
              <div className="py-6 flex items-center justify-center text-slate-600 text-sm">
                Comprobando servicios…
              </div>
            ) : services.length > 0 ? (
              services.map(([name, info]) => (
                <ServiceRow key={name} name={name} info={info} />
              ))
            ) : (
              <div className="py-6 flex items-center justify-center text-red-400 text-sm">
                No se pudo conectar al backend (¿está corriendo en {API_URL}?)
              </div>
            )}
          </div>
        </div>

        {/* First-time guide */}
        <div>
          <h2 className="text-base font-semibold text-slate-100 mb-3">Guía de primer uso</h2>
          <ol className="space-y-2.5">
            {[
              { cmd: 'docker compose up -d', desc: 'Levanta el stack completo (Prometheus, Loki, ChromaDB, Alertmanager, LangFuse)' },
              { desc: 'Verifica arriba que todos los indicadores sean verdes' },
              { cmd: 'python Backend/scripts/seed_chromadb.py', desc: 'Carga los runbooks base en ChromaDB (solo la primera vez)' },
              { desc: 'Listo — vuelve al Dashboard y crea o espera un incidente' },
            ].map((step, i) => (
              <li key={i} className="flex gap-3">
                <span className="text-slate-600 font-mono text-xs shrink-0 mt-1">{i + 1}.</span>
                <div className="space-y-1">
                  <p className="text-sm text-slate-300">{step.desc}</p>
                  {step.cmd && (
                    <pre className="text-xs text-sky-300 font-mono bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5">
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
          className="inline-flex items-center gap-2 bg-sky-600 hover:bg-sky-500 text-white rounded-lg px-5 py-2.5 text-sm font-medium transition-colors"
        >
          Ir al Dashboard →
        </Link>
      </div>
    </div>
  )
}

import { useState, useEffect } from 'react'
import { supabase } from '../lib/supabase'

async function fetchMetrics(incidentId) {
  const { data: { session } } = await supabase.auth.getSession()
  const token = session?.access_token
  const res = await fetch(
    `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/incidents/${incidentId}/metrics`,
    { headers: { Authorization: `Bearer ${token}` } },
  )
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

function fmt(val, unit = '', decimals = 1) {
  if (val === null || val === undefined) return '—'
  return `${Number(val).toFixed(decimals)}${unit}`
}

function UsageBar({ percent, warnAt = 75, critAt = 90 }) {
  if (percent === null || percent === undefined) return null
  const color =
    percent >= critAt ? 'bg-red-500' :
    percent >= warnAt ? 'bg-amber-500' :
    'bg-emerald-500'
  return (
    <div className="mt-1.5 h-1.5 rounded-full bg-slate-800 overflow-hidden">
      <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${Math.min(percent, 100)}%` }} />
    </div>
  )
}

function MetricTile({ label, value, sub, percent, warnAt, critAt, highlight }) {
  const valueColor =
    highlight === 'bad'    ? 'text-red-300' :
    highlight === 'warn'   ? 'text-amber-300' :
    highlight === 'good'   ? 'text-emerald-300' :
    'text-slate-200'

  return (
    <div className="bg-slate-950 border border-slate-800 rounded-lg p-3">
      <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">{label}</p>
      <p className={`text-sm font-semibold font-mono ${valueColor}`}>{value}</p>
      {sub  && <p className="text-[10px] text-slate-600 mt-0.5">{sub}</p>}
      {percent !== undefined && (
        <UsageBar percent={percent} warnAt={warnAt} critAt={critAt} />
      )}
    </div>
  )
}

function ContainerMetrics({ m }) {
  const memHighlight =
    m.mem_percent >= 90 ? 'bad' :
    m.mem_percent >= 75 ? 'warn' : null

  const cpuHighlight =
    m.cpu_percent >= 90 ? 'bad' :
    m.cpu_percent >= 60 ? 'warn' : null

  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
      <MetricTile
        label="Memoria"
        value={fmt(m.mem_usage_mb, ' MB', 0)}
        sub={m.mem_limit_mb ? `límite ${fmt(m.mem_limit_mb, ' MB', 0)} · ${fmt(m.mem_percent, '%')}` : 'sin límite'}
        percent={m.mem_percent}
        warnAt={75} critAt={90}
        highlight={memHighlight}
      />
      <MetricTile
        label="CPU"
        value={fmt(m.cpu_percent, '%')}
        highlight={cpuHighlight}
      />
      <MetricTile
        label="Red entrada"
        value={m.net_in_kbps !== null ? fmt(m.net_in_kbps, ' KB/s') : '—'}
      />
      <MetricTile
        label="Red salida"
        value={m.net_out_kbps !== null ? fmt(m.net_out_kbps, ' KB/s') : '—'}
      />
      <MetricTile
        label="Reinicios (1h)"
        value={m.restarts_1h !== null ? String(m.restarts_1h) : '—'}
        highlight={m.restarts_1h >= 3 ? 'bad' : m.restarts_1h >= 1 ? 'warn' : null}
      />
    </div>
  )
}

function PostgresMetrics({ m }) {
  const connHighlight =
    m.conn_percent >= 90 ? 'bad' :
    m.conn_percent >= 70 ? 'warn' : null

  const cacheHighlight =
    m.cache_hit_percent < 80 ? 'bad' :
    m.cache_hit_percent < 90 ? 'warn' :
    'good'

  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
      <MetricTile
        label="Conexiones"
        value={m.connections !== null ? String(m.connections) : '—'}
        sub={m.max_connections ? `máx ${m.max_connections} · ${fmt(m.conn_percent, '%')}` : null}
        percent={m.conn_percent}
        warnAt={70} critAt={90}
        highlight={connHighlight}
      />
      <MetricTile
        label="Tamaño BD"
        value={fmt(m.db_size_mb, ' MB', 0)}
      />
      <MetricTile
        label="Cache hit ratio"
        value={fmt(m.cache_hit_percent, '%')}
        highlight={cacheHighlight}
      />
      <MetricTile
        label="Deadlocks/min"
        value={fmt(m.deadlocks_per_min, '', 2)}
        highlight={m.deadlocks_per_min > 0 ? 'warn' : null}
      />
      <MetricTile
        label="Transacción más larga"
        value={m.longest_tx_sec !== null ? fmt(m.longest_tx_sec, 's') : '—'}
        highlight={m.longest_tx_sec > 300 ? 'bad' : m.longest_tx_sec > 60 ? 'warn' : null}
      />
    </div>
  )
}

export default function MetricsPanel({ incidentId }) {
  const [metrics, setMetrics] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true) // eslint-disable-line react-hooks/set-state-in-effect
    setError(null)
    fetchMetrics(incidentId)
      .then((data) => { if (!cancelled) { setMetrics(data); setLoading(false) } })
      .catch((e)   => { if (!cancelled) { setError(e.message); setLoading(false) } })
    return () => { cancelled = true }
  }, [incidentId])

  const allNull = metrics && Object.entries(metrics)
    .filter(([k]) => k !== 'type')
    .every(([, v]) => v === null)

  if (loading) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 flex items-center gap-2 text-xs text-slate-500">
        <span className="w-3 h-3 rounded-full border-2 border-slate-600 border-t-slate-400 animate-spin" />
        Consultando Prometheus…
      </div>
    )
  }

  if (error || allNull) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
        <p className="text-xs text-slate-600">
          Métricas no disponibles — Prometheus sin datos para este target.
        </p>
        <p className="text-[10px] text-slate-700 mt-1">
          El stack de monitoreo puede estar apagado o el contenedor ya no existe.
        </p>
      </div>
    )
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-slate-500 uppercase tracking-wider">
          {metrics.type === 'postgres' ? 'PostgreSQL' : 'Contenedor'} · en vivo
        </span>
        <span className="text-[10px] text-slate-700">via Prometheus</span>
      </div>
      {metrics.type === 'postgres'
        ? <PostgresMetrics m={metrics} />
        : <ContainerMetrics m={metrics} />
      }
    </div>
  )
}

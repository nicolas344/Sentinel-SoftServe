import { useState, useEffect, useLayoutEffect, useRef, useCallback, useMemo } from 'react'
import { Search, Plus, Settings, ArrowRight, Terminal } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

const SEVERITY_DOT = {
  critical: 'bg-red-500',
  high:     'bg-orange-500',
  medium:   'bg-yellow-500',
  low:      'bg-green-500',
}

const STATUS_LABEL = {
  detected:           'Detectado',
  investigating:      'Investigando',
  analyzed:           'Analizado',
  awaiting_approval:  'Aprobar',
  executing_solution: 'Ejecutando',
  verifying:          'Verificando',
  resolved:           'Resuelto',
  failed:             'Falló',
}

const STATUS_COLOR = {
  awaiting_approval: 'text-cyan-400',
  resolved:          'text-emerald-400',
  failed:            'text-red-400',
}

export default function CommandPalette({ open, onClose, incidents, onSelectIncident, onNewIncident }) {
  const [query, setQuery] = useState('')
  const [activeIdx, setActiveIdx] = useState(0)
  const inputRef = useRef(null)
  const navigate = useNavigate()

  // Reset state and focus on open
  useLayoutEffect(() => {
    if (open) {
      setQuery('')
      setActiveIdx(0)
      inputRef.current?.focus()
    }
  }, [open])

  // Escape to close
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose() }
    if (open) window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, onClose])

  const filteredIncidents = query.trim()
    ? incidents
        .filter(
          (i) =>
            i.title?.toLowerCase().includes(query.toLowerCase()) ||
            i.target?.toLowerCase().includes(query.toLowerCase()),
        )
        .slice(0, 7)
    : incidents.slice(0, 5)

  const quickActions = useMemo(() => [
    {
      icon: Plus,
      label: 'Nuevo incidente',
      shortcut: 'N',
      action: () => { onClose(); onNewIncident() },
    },
    {
      icon: Settings,
      label: 'Estado del sistema',
      shortcut: 'S',
      action: () => { onClose(); navigate('/setup') },
    },
  ], [onClose, onNewIncident, navigate])

  const allItems = useMemo(() => [
    ...filteredIncidents.map((i, idx) => ({ type: 'incident', data: i, idx })),
    ...(!query ? quickActions.map((a, idx) => ({ type: 'action', data: a, idx: filteredIncidents.length + idx })) : []),
  ], [filteredIncidents, quickActions, query])

  // Arrow key navigation
  useEffect(() => {
    if (!open) return
    const handler = (e) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setActiveIdx((i) => Math.min(i + 1, allItems.length - 1))
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setActiveIdx((i) => Math.max(i - 1, 0))
      } else if (e.key === 'Enter') {
        e.preventDefault()
        const item = allItems[activeIdx]
        if (!item) return
        if (item.type === 'incident') { onClose(); onSelectIncident(item.data) }
        else item.data.action()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, allItems, activeIdx, onClose, onSelectIncident])

  const handleIncidentClick = useCallback((incident) => {
    onClose()
    onSelectIncident(incident)
  }, [onClose, onSelectIncident])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[14vh] px-4 animate-fade-in">
      <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm" onClick={onClose} />

      <div className="relative w-full max-w-lg bg-slate-900 border border-slate-700 rounded-xl shadow-2xl overflow-hidden animate-slide-up">

        {/* Input row */}
        <div className="flex items-center gap-3 px-4 py-3.5 border-b border-slate-800">
          <Search className="w-4 h-4 text-slate-500 shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => { setQuery(e.target.value); setActiveIdx(0) }}
            placeholder="Buscar incidentes o acciones..."
            className="flex-1 bg-transparent text-sm text-slate-200 placeholder-slate-500 outline-none"
          />
          <div className="flex items-center gap-1 shrink-0">
            <kbd className="text-[10px] text-slate-600 bg-slate-800 border border-slate-700 rounded px-1.5 py-0.5 font-mono">⌘K</kbd>
          </div>
        </div>

        {/* Results */}
        <div className="max-h-[340px] overflow-y-auto py-2">

          {filteredIncidents.length > 0 && (
            <section>
              <p className="px-4 py-1.5 text-[10px] font-semibold text-slate-600 uppercase tracking-widest">
                {query ? 'Resultados' : 'Incidentes recientes'}
              </p>
              {filteredIncidents.map((incident, idx) => (
                <button
                  key={incident.id}
                  onClick={() => handleIncidentClick(incident)}
                  onMouseEnter={() => setActiveIdx(idx)}
                  className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors ${
                    activeIdx === idx ? 'bg-slate-800' : 'hover:bg-slate-800/50'
                  }`}
                >
                  <span className={`w-2 h-2 rounded-full shrink-0 ${SEVERITY_DOT[incident.severity] || 'bg-slate-500'}`} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-slate-200 truncate">{incident.title}</p>
                    <p className="text-xs text-slate-500 truncate font-mono">{incident.target}</p>
                  </div>
                  {incident.status && (
                    <span className={`text-xs shrink-0 ${STATUS_COLOR[incident.status] || 'text-slate-500'}`}>
                      {STATUS_LABEL[incident.status] || incident.status}
                    </span>
                  )}
                  <ArrowRight className="w-3 h-3 text-slate-600 shrink-0" />
                </button>
              ))}
            </section>
          )}

          {!query && (
            <section className="mt-1">
              <p className="px-4 py-1.5 text-[10px] font-semibold text-slate-600 uppercase tracking-widest">
                Acciones rápidas
              </p>
              {quickActions.map(({ icon: Icon, label, action, shortcut }, idx) => {
                const globalIdx = filteredIncidents.length + idx
                return (
                  <button
                    key={label}
                    onClick={action}
                    onMouseEnter={() => setActiveIdx(globalIdx)}
                    className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors ${
                      activeIdx === globalIdx ? 'bg-slate-800' : 'hover:bg-slate-800/50'
                    }`}
                  >
                    <Icon className="w-4 h-4 text-slate-400 shrink-0" />
                    <span className="flex-1 text-sm text-slate-300">{label}</span>
                    <kbd className="text-[10px] text-slate-600 bg-slate-800 border border-slate-700 rounded px-1.5 py-0.5 font-mono shrink-0">
                      {shortcut}
                    </kbd>
                  </button>
                )
              })}
            </section>
          )}

          {query && filteredIncidents.length === 0 && (
            <div className="flex flex-col items-center gap-2 py-10 text-slate-600">
              <Terminal className="w-6 h-6" />
              <p className="text-sm">Sin resultados para "{query}"</p>
            </div>
          )}
        </div>

        {/* Footer hints */}
        <div className="flex items-center gap-5 px-4 py-2.5 border-t border-slate-800 bg-slate-950/30">
          {[['↵', 'seleccionar'], ['↑↓', 'navegar'], ['esc', 'cerrar']].map(([key, label]) => (
            <span key={key} className="flex items-center gap-1.5 text-[10px] text-slate-600">
              <kbd className="bg-slate-800 border border-slate-700 rounded px-1 py-0.5 font-mono">{key}</kbd>
              {label}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}

import { useState, useEffect, useCallback } from 'react'
import { supabase } from '../lib/supabase'

// Parsea el texto raw del runbook en secciones { key, value, items[] }
function parseRunbookContent(content) {
  if (!content) return []
  const lines = content.split('\n')
  const sections = []
  let current = null

  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed) continue
    const headerMatch = trimmed.match(/^([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ_\s]{1,28}):\s*(.*)$/)
    if (headerMatch && !/^\d/.test(headerMatch[1])) {
      current = { key: headerMatch[1].trim(), value: headerMatch[2].trim(), items: [] }
      sections.push(current)
    } else if (current) {
      const bullet = trimmed.match(/^[-*•]\s+(.+)$/) || trimmed.match(/^(\d+)\.\s+(.+)$/)
      if (bullet) {
        current.items.push({ num: bullet[2] ? bullet[1] : null, text: bullet[2] || bullet[1] })
      } else if (current.value === '' && current.items.length === 0) {
        current.value = trimmed
      } else {
        current.items.push({ num: null, text: trimmed })
      }
    }
  }
  return sections
}

const SECTION_ACCENT = {
  'TIPO':    'text-sky-400',
  'SEÑALES': 'text-amber-400',
  'CAUSA':   'text-red-400',
  'PASOS':   'text-emerald-400',
  'ACCIÓN':  'text-emerald-400',
  'ACCIONES':'text-emerald-400',
  'NOTAS':   'text-slate-400',
  'FUENTE':  'text-slate-500',
}

function RunbookContent({ content }) {
  const sections = parseRunbookContent(content)
  if (sections.length === 0) {
    return (
      <pre className="text-xs text-slate-300 font-mono whitespace-pre-wrap leading-relaxed">
        {content}
      </pre>
    )
  }
  return (
    <div className="space-y-3">
      {sections.map((sec, i) => {
        const accentKey = Object.keys(SECTION_ACCENT).find(k => sec.key.toUpperCase().startsWith(k))
        const accent = SECTION_ACCENT[accentKey] || 'text-slate-400'
        return (
          <div key={i}>
            <p className={`text-[10px] font-semibold uppercase tracking-wider mb-1 ${accent}`}>
              {sec.key}
            </p>
            {sec.value && (
              <p className="text-xs text-slate-300 leading-relaxed">{sec.value}</p>
            )}
            {sec.items.length > 0 && (
              <ul className="mt-1 space-y-1">
                {sec.items.map((item, j) => (
                  <li key={j} className="flex items-start gap-2 text-xs text-slate-400 leading-relaxed">
                    <span className="shrink-0 text-slate-600 font-mono mt-0.5">
                      {item.num ? `${item.num}.` : '·'}
                    </span>
                    <span>{item.text}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )
      })}
    </div>
  )
}

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function fetchRunbooks(incidentId, q) {
  const { data: { session } } = await supabase.auth.getSession()
  const url = new URL(`${API_URL}/api/incidents/${incidentId}/runbooks`)
  if (q) url.searchParams.set('q', q)
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${session.access_token}` },
  })
  if (!res.ok) throw new Error('Error al cargar runbooks')
  return res.json()
}

export default function RunbookViewer({ incidentId }) {
  const [runbooks, setRunbooks] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [expanded, setExpanded] = useState(null)

  const load = useCallback(async (q = '') => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchRunbooks(incidentId, q)
      setRunbooks(data)
      setExpanded(data.length > 0 ? 0 : null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [incidentId])

  useEffect(() => { load() }, [load])

  const handleSearch = (e) => {
    e.preventDefault()
    load(search.trim())
  }

  return (
    <div className="space-y-3">
      <form onSubmit={handleSearch} className="flex gap-2">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Buscar en runbooks..."
          className="flex-1 bg-slate-900 border border-slate-700 rounded-md px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-slate-500"
        />
        <button
          type="submit"
          className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded-md text-xs transition-colors"
        >
          Buscar
        </button>
      </form>

      {loading && (
        <div className="flex items-center gap-2 text-xs text-slate-500 py-2">
          <span className="w-3 h-3 rounded-full border-2 border-slate-600 border-t-slate-400 animate-spin" />
          Buscando runbooks relevantes...
        </div>
      )}

      {error && (
        <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-md px-3 py-2">
          {error}
        </p>
      )}

      {!loading && !error && runbooks.length === 0 && (
        <p className="text-xs text-slate-500 py-2">No se encontraron runbooks para este incidente.</p>
      )}

      <div className="space-y-2">
        {runbooks.map((rb, i) => (
          <div key={i} className="border border-slate-800 rounded-lg overflow-hidden">
            <button
              onClick={() => setExpanded(expanded === i ? null : i)}
              className="w-full flex items-center justify-between px-4 py-2.5 bg-slate-900 hover:bg-slate-800 transition-colors text-left"
            >
              <span className="text-xs font-medium text-slate-200 truncate pr-4">{rb.title}</span>
              <span className="text-slate-500 text-xs shrink-0">
                {expanded === i ? '▲' : '▼'}
              </span>
            </button>
            {expanded === i && (
              <div className="px-4 py-3 bg-slate-950 max-h-72 overflow-y-auto">
                <RunbookContent content={rb.content} />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

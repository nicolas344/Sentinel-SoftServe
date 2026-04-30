/**
 * AgentReasoningPanel
 *
 * Renderiza el razonamiento del agente como UI "agentic" en vez de <pre> plano:
 *   - Identidad del agente (docker / kubernetes / postgres / …)
 *   - Timeline de estado (clasificado → investigando → analizado)
 *   - Chips de tools invocadas
 *   - Contador de incidentes similares recordados
 *   - Cada sección del análisis en su propia tarjeta con acento de color
 *
 * Parsea el markdown que el Supervisor escribe en `agent_reasoning`.
 * Sin dependencias externas de markdown.
 */

import { useEffect, useMemo, useState } from 'react'

// ── Metadatos por dominio ─────────────────────────────────────────────────────

const AGENT_STYLES = {
  docker: {
    label: 'Docker Agent',
    subtitle: 'Especialista en contenedores Docker',
    letter: 'D',
    ring: 'ring-sky-500/40',
    glow: 'from-sky-500/20 to-blue-600/10',
    badge: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
  },
  podman: {
    label: 'Podman Agent',
    subtitle: 'Especialista en contenedores Podman',
    letter: 'P',
    ring: 'ring-purple-500/40',
    glow: 'from-purple-500/20 to-violet-600/10',
    badge: 'bg-purple-500/15 text-purple-300 border-purple-500/30',
  },
  kubernetes: {
    label: 'Kubernetes Agent',
    subtitle: 'Especialista en workloads Kubernetes',
    letter: 'K',
    ring: 'ring-cyan-500/40',
    glow: 'from-cyan-500/20 to-sky-600/10',
    badge: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
  },
  postgres: {
    label: 'Postgres Agent',
    subtitle: 'Especialista en bases de datos PostgreSQL',
    letter: 'P',
    ring: 'ring-emerald-500/40',
    glow: 'from-emerald-500/20 to-teal-600/10',
    badge: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  },
  default: {
    label: 'Agent',
    subtitle: 'Especialista genérico',
    letter: 'A',
    ring: 'ring-slate-500/40',
    glow: 'from-slate-500/20 to-slate-700/10',
    badge: 'bg-slate-500/15 text-slate-300 border-slate-500/30',
  },
}

// Cada sección del markdown → color del acento y título corto para mostrar
const SECTION_STYLES = {
  'causa raíz':              { accent: 'border-l-red-500/60',     label: 'Causa raíz',        tone: 'text-red-300' },
  'evidencia':               { accent: 'border-l-amber-500/60',   label: 'Evidencia',          tone: 'text-amber-300' },
  '¿ya habíamos visto esto?': { accent: 'border-l-violet-500/60',  label: 'Memoria del agente', tone: 'text-violet-300' },
  'acciones recomendadas':   { accent: 'border-l-emerald-500/60', label: 'Acciones',          tone: 'text-emerald-300' },
  'evaluación de urgencia':  { accent: 'border-l-orange-500/60',  label: 'Urgencia',           tone: 'text-orange-300' },
  'clasificación inicial':   { accent: 'border-l-sky-500/60',     label: 'Clasificación',      tone: 'text-sky-300' },
  'investigación':           { accent: 'border-l-blue-500/60',    label: 'Investigación',      tone: 'text-blue-300' },
  'error de routing':        { accent: 'border-l-red-500/60',     label: 'Routing',            tone: 'text-red-300' },
  'error':                   { accent: 'border-l-red-500/60',     label: 'Error',              tone: 'text-red-300' },
}

// ── Parser de markdown ligero ────────────────────────────────────────────────

/**
 * Parsea el texto markdown del agente y extrae:
 *   - agentName: "docker" / "kubernetes" / "postgres" (si aparece)
 *   - incidentType: valor de **Tipo detectado:** `oom`
 *   - tools: lista de nombres de tools invocadas
 *   - similarCount: cuántos incidentes similares recordó
 *   - sections: [{ key, title, body }]
 */
function parseReasoning(raw) {
  if (!raw) return { sections: [], tools: [], similarCount: 0 }

  // Extraer agente de "Investigación (agente `docker`)"
  const agentMatch = raw.match(/agente\s+`([a-z_-]+)`/i)
  const agentName = agentMatch ? agentMatch[1].toLowerCase() : null

  // Extraer tipo de "**Tipo detectado:** `oom`"
  const typeMatch = raw.match(/\*\*Tipo detectado:\*\*\s*`([^`]+)`/i)
  const incidentType = typeMatch ? typeMatch[1] : null

  // Extraer "Tools invocadas: `docker_inspect` — `docker_logs`" (o "ninguna")
  const toolsLine = raw.match(/Tools invocadas:\s*([^\n.]+)/i)
  let tools = []
  if (toolsLine) {
    const body = toolsLine[1]
    if (!/ninguna/i.test(body)) {
      tools = [...body.matchAll(/`([^`]+)`/g)].map((m) => m[1])
    }
  }

  // Extraer "Incidentes similares encontrados: N"
  const similarMatch = raw.match(/Incidentes similares encontrados:\s*(\d+)/i)
  const similarCount = similarMatch ? parseInt(similarMatch[1], 10) : 0

  // Partir por "## " al inicio de línea
  const chunks = raw.split(/\n##\s+/m).map((c, i) => (i === 0 ? c.replace(/^##\s+/, '') : c))
  const sections = chunks
    .map((chunk) => {
      const lines = chunk.split('\n')
      const title = (lines.shift() || '').trim()
      // Eliminar separadores horizontales tipo "---"
      const body = lines
        .join('\n')
        .replace(/^\s*---\s*$/gm, '')
        .trim()
      return { title, body }
    })
    .filter((s) => s.title)

  return { agentName, incidentType, tools, similarCount, sections }
}

// ── Renderizador de markdown inline (negritas, código, listas) ───────────────

function renderInline(text) {
  // Orden: primero code (`...`), después bold (**...**), después italic (_..._)
  const parts = []
  let remaining = text
  let keyCounter = 0

  const pattern = /(`[^`]+`)|(\*\*[^*]+\*\*)|(_[^_\n]+_)/

  while (remaining.length) {
    const match = remaining.match(pattern)
    if (!match) {
      parts.push(<span key={keyCounter++}>{remaining}</span>)
      break
    }
    const idx = match.index
    if (idx > 0) parts.push(<span key={keyCounter++}>{remaining.slice(0, idx)}</span>)
    const token = match[0]
    if (token.startsWith('`')) {
      parts.push(
        <code
          key={keyCounter++}
          className="px-1.5 py-0.5 rounded bg-slate-800/80 border border-slate-700/60 text-[11px] font-mono text-sky-300"
        >
          {token.slice(1, -1)}
        </code>
      )
    } else if (token.startsWith('**')) {
      parts.push(
        <strong key={keyCounter++} className="text-slate-100 font-semibold">
          {token.slice(2, -2)}
        </strong>
      )
    } else if (token.startsWith('_')) {
      parts.push(
        <em key={keyCounter++} className="text-slate-400">
          {token.slice(1, -1)}
        </em>
      )
    }
    remaining = remaining.slice(idx + token.length)
  }
  return parts
}

function renderBody(body) {
  if (!body) return null
  const blocks = body.split(/\n\n+/).map((b) => b.trim()).filter(Boolean)

  return blocks.map((block, i) => {
    const lines = block.split('\n').map((l) => l.trimEnd())

    // Lista numerada (1. ..., 2. ...)
    if (lines.every((l) => /^\d+\.\s/.test(l))) {
      return (
        <ol key={i} className="space-y-1.5 pl-1">
          {lines.map((l, j) => {
            const m = l.match(/^(\d+)\.\s(.*)$/)
            return (
              <li key={j} className="flex gap-2.5">
                <span className="text-slate-600 text-xs font-mono shrink-0 mt-0.5">
                  {m[1].padStart(2, '0')}
                </span>
                <span className="text-sm text-slate-300 leading-relaxed">{renderInline(m[2])}</span>
              </li>
            )
          })}
        </ol>
      )
    }

    // Lista con viñetas
    if (lines.every((l) => /^[-*]\s/.test(l))) {
      return (
        <ul key={i} className="space-y-1.5 pl-1">
          {lines.map((l, j) => (
            <li key={j} className="flex gap-2.5">
              <span className="text-slate-600 shrink-0 mt-1.5">•</span>
              <span className="text-sm text-slate-300 leading-relaxed">
                {renderInline(l.replace(/^[-*]\s/, ''))}
              </span>
            </li>
          ))}
        </ul>
      )
    }

    // Párrafo normal
    return (
      <p key={i} className="text-sm text-slate-300 leading-relaxed">
        {renderInline(lines.join(' '))}
      </p>
    )
  })
}

// ── Subcomponentes ───────────────────────────────────────────────────────────

function AgentHeader({ agentName, incidentType, tools, similarCount, status }) {
  const style = AGENT_STYLES[agentName] || AGENT_STYLES.default
  const isLive = status === 'investigating' || status === 'detected'

  return (
    <div
      className={`relative overflow-hidden rounded-xl border border-slate-800 bg-gradient-to-br ${style.glow} p-5 animate-fade-in-up`}
    >
      <div className="flex items-start gap-4">
        {/* Avatar */}
        <div className="relative shrink-0">
          <div
            className={`w-12 h-12 rounded-full bg-slate-900 border border-slate-700 ring-2 ${style.ring} flex items-center justify-center text-lg font-bold text-slate-100 ${
              isLive ? 'animate-agent-glow' : ''
            }`}
          >
            {style.letter}
          </div>
          {isLive && (
            <span className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full bg-emerald-400 ring-2 ring-slate-950 animate-pulse" />
          )}
        </div>

        {/* Identidad + meta */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold text-slate-100">{style.label}</h3>
            <span
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium border ${style.badge}`}
            >
              {isLive ? 'analizando' : 'listo'}
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">{style.subtitle}</p>

          {/* Chips de metadatos */}
          <div className="flex items-center gap-2 flex-wrap mt-3">
            {incidentType && (
              <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-slate-900/80 border border-slate-700/60 text-[11px] text-slate-300">
                <span className="w-1 h-1 rounded-full bg-slate-500" />
                {incidentType}
              </span>
            )}
            <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-slate-900/80 border border-slate-700/60 text-[11px] text-slate-300">
              <span className="w-1 h-1 rounded-full bg-violet-400" />
              {similarCount} similar{similarCount === 1 ? '' : 'es'} recordado{similarCount === 1 ? '' : 's'}
            </span>
            <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-slate-900/80 border border-slate-700/60 text-[11px] text-slate-300">
              <span className="w-1 h-1 rounded-full bg-amber-400" />
              {tools.length} tool{tools.length === 1 ? '' : 's'}
            </span>
          </div>

          {/* Tools invocadas */}
          {tools.length > 0 && (
            <div className="flex items-center gap-1.5 flex-wrap mt-2.5">
              {tools.map((t, i) => (
                <span
                  key={`${t}-${i}`}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded border border-amber-500/20 bg-amber-500/5 text-[10px] font-mono text-amber-300"
                >
                  <span className="text-amber-500/70">⌘</span>
                  {t}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function Timeline({ status }) {
  // Status flow: detected → investigating → analyzed → awaiting_approval → executing_solution → verifying → (resolved | failed)
  const steps = [
    { key: 'detected', label: 'Detectado' },
    { key: 'investigating', label: 'Investigando' },
    { key: 'analyzed', label: 'Analizado' },
    { key: 'awaiting_approval', label: 'Esperando aprobación' },
    { key: 'executing_solution', label: 'Ejecutando solución' },
    { key: 'verifying', label: 'Verificando' },
  ]
  const currentIdx = steps.findIndex((step) => step.key === status)
  const reachedTerminal = status === 'resolved' || status === 'failed'

  return (
    <div className="flex items-center gap-1 flex-wrap">
      {steps.map((step, i) => {
        const isDone = reachedTerminal ? true : i < currentIdx
        const isCurrent = !reachedTerminal && i === currentIdx
        return (
          <div key={step.key} className="flex items-center gap-1">
            <div
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[10px] font-medium transition-colors ${
                isDone
                  ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                  : isCurrent
                  ? 'bg-sky-500/10 border-sky-500/40 text-sky-200'
                  : 'bg-slate-900 border-slate-800 text-slate-600'
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  isDone ? 'bg-emerald-400' : isCurrent ? 'bg-sky-400 animate-pulse' : 'bg-slate-700'
                }`}
              />
              {step.label}
            </div>
            {i < steps.length - 1 && (
              <div
                className={`w-2 h-px ${isDone || isCurrent ? 'bg-slate-700' : 'bg-slate-800'}`}
              />
            )}
          </div>
        )
      })}

      <div className="w-2 h-px bg-slate-800" />

      <div
        className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[10px] font-medium transition-colors ${
          status === 'resolved'
            ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
            : 'bg-slate-900 border-slate-800 text-slate-600'
        }`}
      >
        <span
          className={`w-1.5 h-1.5 rounded-full ${status === 'resolved' ? 'bg-emerald-400' : 'bg-slate-700'}`}
        />
        Resuelto
      </div>

      <div
        className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[10px] font-medium transition-colors ${
          status === 'failed'
            ? 'bg-red-500/10 border-red-500/30 text-red-300'
            : 'bg-slate-900 border-slate-800 text-slate-600'
        }`}
      >
        <span
          className={`w-1.5 h-1.5 rounded-full ${status === 'failed' ? 'bg-red-400' : 'bg-slate-700'}`}
        />
        Falló
      </div>
    </div>
  )
}

function SectionCard({ title, body, index = 0 }) {
  const titleKey = title.toLowerCase().replace(/\s*\([^)]*\)/g, '').trim()
  const style = SECTION_STYLES[titleKey] || {
    accent: 'border-l-slate-600',
    label: title,
    tone: 'text-slate-300',
  }

  return (
    <div
      className={`rounded-lg border border-slate-800 bg-slate-900/50 border-l-2 ${style.accent} pl-4 pr-4 py-3 animate-fade-in-up`}
      style={{ animationDelay: `${index * 80}ms` }}
    >
      <h4 className={`text-[11px] font-semibold uppercase tracking-wider mb-2 ${style.tone}`}>
        {style.label}
      </h4>
      <div className="space-y-2.5">{renderBody(body)}</div>
    </div>
  )
}

/** Tres dots pulsantes estilo Claude / ChatGPT mientras escribe. */
function ThinkingDots({ className = '' }) {
  return (
    <span className={`inline-flex items-center gap-1 ${className}`}>
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="inline-block w-1.5 h-1.5 rounded-full bg-sky-400 animate-thinking-dot"
          style={{ animationDelay: `${i * 180}ms` }}
        />
      ))}
    </span>
  )
}

/** Texto que rota cíclicamente mostrando qué está haciendo el agente. */
function RotatingStatus({ phase }) {
  // phase: 'detected' (recién creado) | 'investigating' (ya clasificó)
  const messages = useMemo(
    () =>
      phase === 'detected'
        ? [
            'Recibiendo alerta',
            'Preparando contexto',
            'Clasificando el tipo de incidente',
          ]
        : [
            'Leyendo runbooks relacionados',
            'Buscando incidentes similares en memoria',
            'Revisando los logs del contenedor',
            'Invocando tools de diagnóstico',
            'Redactando el análisis final',
          ],
    [phase]
  )

  const [idx, setIdx] = useState(0)
  useEffect(() => {
    const timer = window.setInterval(() => {
      setIdx((i) => (i + 1) % messages.length)
    }, 1800)
    return () => window.clearInterval(timer)
  }, [messages.length])

  return (
    <span className="inline-flex items-baseline gap-1">
      <span
        key={idx}
        className="text-sm text-slate-300 animate-fade-in-up inline-block"
      >
        {messages[idx]}
      </span>
      <ThinkingDots className="ml-1" />
    </span>
  )
}

/** Skeleton con shimmer — simula "ya casi llega la respuesta". */
function ShimmerLines({ widths = ['90%', '70%', '95%', '55%'] }) {
  return (
    <div className="space-y-2.5">
      {widths.map((w, i) => (
        <div
          key={i}
          className="h-2 rounded bg-slate-800 animate-shimmer"
          style={{ width: w }}
        />
      ))}
    </div>
  )
}

function AnalyzingPlaceholder({ phase }) {
  const steps =
    phase === 'detected'
      ? [
          { label: 'Incidente recibido',          state: 'done' },
          { label: 'Clasificando con el LLM',     state: 'running' },
          { label: 'Consultando memoria',         state: 'pending' },
          { label: 'Redactando diagnóstico',      state: 'pending' },
        ]
      : [
          { label: 'Incidente recibido',          state: 'done' },
          { label: 'Clasificado',                 state: 'done' },
          { label: 'Investigando con el especialista', state: 'running' },
          { label: 'Redactando diagnóstico',      state: 'pending' },
        ]

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/40 overflow-hidden">
      {/* Barra superior con barras de ecualizador + estado */}
      <div className="flex items-center gap-3 px-5 py-4 border-b border-slate-800/70 bg-slate-900/60">
        <div className="flex items-end gap-0.5 h-4 w-6 shrink-0">
          {[0, 1, 2, 3].map((b) => (
            <span
              key={b}
              className="w-1 bg-sky-400 rounded-sm animate-equalizer"
              style={{ animationDelay: `${b * 150}ms` }}
            />
          ))}
        </div>
        <RotatingStatus phase={phase} />
      </div>

      {/* Lista de pasos del pipeline */}
      <div className="px-5 py-4 space-y-2.5">
        {steps.map((step, i) => (
          <div key={i} className="flex items-center gap-2.5">
            {step.state === 'done' && (
              <span className="w-4 h-4 rounded-full bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center shrink-0">
                <svg className="w-2.5 h-2.5 text-emerald-400" viewBox="0 0 20 20" fill="currentColor">
                  <path
                    fillRule="evenodd"
                    d="M16.7 5.3a1 1 0 010 1.4l-8 8a1 1 0 01-1.4 0l-4-4a1 1 0 111.4-1.4L8 12.6l7.3-7.3a1 1 0 011.4 0z"
                    clipRule="evenodd"
                  />
                </svg>
              </span>
            )}
            {step.state === 'running' && (
              <span className="w-4 h-4 rounded-full border-2 border-sky-500/30 border-t-sky-400 animate-spin-slow shrink-0" />
            )}
            {step.state === 'pending' && (
              <span className="w-4 h-4 rounded-full border border-slate-700 shrink-0" />
            )}
            <span
              className={`text-xs ${
                step.state === 'done'
                  ? 'text-slate-400'
                  : step.state === 'running'
                  ? 'text-slate-200 font-medium'
                  : 'text-slate-600'
              }`}
            >
              {step.label}
            </span>
          </div>
        ))}
      </div>

      {/* Shimmer de texto "por llegar" */}
      <div className="px-5 pb-5">
        <ShimmerLines />
      </div>
    </div>
  )
}

// ── Componente principal ─────────────────────────────────────────────────────

export default function AgentReasoningPanel({ reasoning, status }) {
  const parsed = useMemo(() => parseReasoning(reasoning), [reasoning])

  const isThinking = status === 'detected' || status === 'investigating'

  // 1. Aún no hay nada escrito → skeleton + pasos del pipeline
  if (!reasoning || reasoning.trim() === '') {
    return (
      <div className="space-y-3">
        <Timeline status={status} />
        <AnalyzingPlaceholder phase={status} />
      </div>
    )
  }

  // 2. Hay clasificación pero aún no análisis completo (solo 1 sección: "Clasificación inicial")
  const HIDDEN_IN_BODY = new Set(['clasificación inicial', 'investigación'])
  const bodySections = parsed.sections.filter((s) => {
    const k = s.title.toLowerCase().replace(/\s*\([^)]*\)/g, '').trim()
    return !HIDDEN_IN_BODY.has(k)
  })
  const stillInvestigating = isThinking && bodySections.length === 0

  return (
    <div className="space-y-4">
      <AgentHeader
        agentName={parsed.agentName}
        incidentType={parsed.incidentType}
        tools={parsed.tools}
        similarCount={parsed.similarCount}
        status={status}
      />
      <Timeline status={status} />

      {stillInvestigating && <AnalyzingPlaceholder phase="investigating" />}

      {bodySections.length > 0 && (
        <div className="space-y-3">
          {bodySections.map((s, i) => (
            <SectionCard key={`${s.title}-${i}`} title={s.title} body={s.body} index={i} />
          ))}
          {/* Cursor parpadeante si el agente aún está activo pero ya mostró contenido */}
          {isThinking && (
            <div className="flex items-center gap-2 pl-4 text-slate-500 text-xs">
              <ThinkingDots />
              <span>El agente sigue trabajando</span>
            </div>
          )}
        </div>
      )}

      {/* Fallback — si no pudimos parsear secciones pero hay texto */}
      {!stillInvestigating && bodySections.length === 0 && (
        <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-4 animate-fade-in-up">
          <div className="space-y-2.5">{renderBody(reasoning)}</div>
        </div>
      )}
    </div>
  )
}

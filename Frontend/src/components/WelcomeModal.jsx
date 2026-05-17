import { useState, useEffect } from 'react'
import { AlertTriangle, Bot, CheckCircle2, X, ChevronRight, ChevronLeft, Zap } from 'lucide-react'

const STORAGE_KEY = 'sentinel_welcomed_v1'

const SLIDES = [
  {
    id: 'detect',
    Icon: AlertTriangle,
    iconColor: 'text-red-400',
    gradientFrom: 'from-red-500/20',
    gradientTo: 'to-orange-500/10',
    ring: 'ring-red-500/30',
    tag: 'Detección automática',
    tagClass: 'bg-red-500/10 text-red-400 border border-red-500/20',
    accent: 'bg-sky-500',
    title: 'Sentinel detecta alertas en tiempo real',
    body: 'Prometheus y Alertmanager notifican a Sentinel automáticamente. Cada falla crea un incidente con toda la información relevante al instante — sin intervención manual.',
    visual: 'ping',
  },
  {
    id: 'analyze',
    Icon: Bot,
    iconColor: 'text-sky-300',
    gradientFrom: 'from-sky-500/20',
    gradientTo: 'to-blue-600/10',
    ring: 'ring-sky-500/30',
    tag: 'Análisis con IA',
    tagClass: 'bg-sky-500/10 text-sky-400 border border-sky-500/20',
    accent: 'bg-sky-500',
    title: 'Un agente especializado investiga',
    body: 'El agente lee logs, métricas y runbooks para diagnosticar la causa raíz. Consulta incidentes similares en memoria y propone la solución con mayor probabilidad de éxito.',
    visual: 'thinking',
  },
  {
    id: 'approve',
    Icon: CheckCircle2,
    iconColor: 'text-emerald-400',
    gradientFrom: 'from-emerald-500/20',
    gradientTo: 'to-teal-600/10',
    ring: 'ring-emerald-500/30',
    tag: 'Control total',
    tagClass: 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20',
    accent: 'bg-sky-500',
    title: 'Tú apruebas — Sentinel ejecuta y verifica',
    body: 'Revisas el comando propuesto y lo apruebas con un clic. Sentinel lo ejecuta y confirma automáticamente que el servicio se recuperó. Nada se ejecuta sin tu aprobación.',
    visual: 'glow',
  },
]

function SlideVisual({ slide }) {
  const { Icon, iconColor, gradientFrom, gradientTo, ring, visual } = slide
  return (
    <div className={`relative w-24 h-24 rounded-2xl bg-gradient-to-br ${gradientFrom} ${gradientTo} ring-1 ${ring} flex items-center justify-center mx-auto`}>
      <Icon className={`w-11 h-11 ${iconColor}`} />

      {visual === 'ping' && (
        <>
          <span className="absolute inset-0 rounded-2xl animate-ping opacity-10 bg-red-500" />
          <span className="absolute -inset-2 rounded-3xl animate-ping opacity-5 bg-red-400" style={{ animationDelay: '0.4s' }} />
        </>
      )}

      {visual === 'thinking' && (
        <div className="absolute -bottom-3 left-1/2 -translate-x-1/2 flex gap-1">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="w-1.5 h-1.5 rounded-full bg-sky-400 animate-thinking-dot"
              style={{ animationDelay: `${i * 180}ms` }}
            />
          ))}
        </div>
      )}

      {visual === 'glow' && (
        <span className="absolute inset-0 rounded-2xl ring-2 ring-emerald-400/30 animate-pulse" />
      )}
    </div>
  )
}

export default function WelcomeModal({ onClose }) {
  const [slide, setSlide] = useState(0)
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    requestAnimationFrame(() => setMounted(true))
  }, [])

  const handleClose = () => {
    localStorage.setItem(STORAGE_KEY, 'true')
    onClose()
  }

  const current = SLIDES[slide]
  const isLast = slide === SLIDES.length - 1

  return (
    <div className={`fixed inset-0 z-50 flex items-center justify-center p-4 transition-opacity duration-300 ${mounted ? 'opacity-100' : 'opacity-0'}`}>
      <div className="absolute inset-0 bg-slate-950/85 backdrop-blur-md animate-fade-in" onClick={handleClose} />

      <div className={`relative w-full max-w-md bg-slate-900 border border-slate-700/80 rounded-2xl shadow-2xl overflow-hidden transition-all duration-300 ${mounted ? 'scale-100 translate-y-0' : 'scale-95 translate-y-4'}`}>

        {/* Progress bar */}
        <div className="h-0.5 bg-slate-800">
          <div
            className="h-full bg-sky-500 transition-all duration-500 ease-out"
            style={{ width: `${((slide + 1) / SLIDES.length) * 100}%` }}
          />
        </div>

        {/* Close */}
        <button
          onClick={handleClose}
          className="absolute top-4 right-4 text-slate-500 hover:text-slate-300 transition-colors z-10 p-1 rounded-lg hover:bg-slate-800"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Body */}
        <div className="px-8 pt-8 pb-6">
          <SlideVisual slide={current} />

          <div className="mt-7 text-center">
            <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${current.tagClass} mb-4`}>
              {current.tag}
            </span>
            <h2 className="text-lg font-semibold text-slate-100 mb-3 leading-snug">
              {current.title}
            </h2>
            <p className="text-sm text-slate-400 leading-relaxed">
              {current.body}
            </p>
          </div>
        </div>

        {/* Navigation */}
        <div className="flex items-center justify-between px-8 pb-7">
          <button
            onClick={() => setSlide((s) => Math.max(0, s - 1))}
            disabled={slide === 0}
            className="p-2 rounded-lg text-slate-500 hover:text-slate-300 hover:bg-slate-800 disabled:opacity-0 disabled:pointer-events-none transition-all"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>

          {/* Dots */}
          <div className="flex items-center gap-2">
            {SLIDES.map((_, i) => (
              <button
                key={i}
                onClick={() => setSlide(i)}
                className={`rounded-full transition-all duration-300 ${
                  i === slide
                    ? 'w-6 h-2 bg-sky-500'
                    : 'w-2 h-2 bg-slate-700 hover:bg-slate-500'
                }`}
              />
            ))}
          </div>

          {isLast ? (
            <button
              onClick={handleClose}
              className="flex items-center gap-1.5 bg-sky-600 hover:bg-sky-500 text-white rounded-lg px-4 py-2 text-xs font-semibold transition-colors"
            >
              Comenzar <ChevronRight className="w-3.5 h-3.5" />
            </button>
          ) : (
            <button
              onClick={() => setSlide((s) => s + 1)}
              className="flex items-center gap-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg px-4 py-2 text-xs font-medium transition-colors"
            >
              Siguiente <ChevronRight className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}


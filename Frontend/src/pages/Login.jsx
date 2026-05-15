import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Shield, Mail, Lock, ArrowRight, AlertCircle } from 'lucide-react'
import { useAuth } from '../contexts/useAuth'

export default function Login() {
  const { signIn } = useAuth()
  const navigate = useNavigate()

  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState(null)
  const [loading, setLoading]   = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    const { error } = await signIn(email, password)
    if (error) {
      setError(error.message)
    } else {
      navigate('/')
    }
    setLoading(false)
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 px-4">
      <div className="w-full max-w-sm">

        {/* Brand */}
        <div className="flex items-center gap-3 mb-6 justify-center">
          <div className="w-10 h-10 rounded-xl bg-sky-600/20 border border-sky-500/30 flex items-center justify-center">
            <Shield className="w-5 h-5 text-sky-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-50 leading-none">Sentinel</h1>
            <p className="text-xs text-slate-500 mt-0.5">Incident Triage Copilot</p>
          </div>
        </div>

        {/* Product description */}
        <div className="mb-6 space-y-2">
          {[
            { icon: AlertCircle, text: 'Detecta incidentes automáticamente vía Prometheus y cAdvisor' },
            { icon: ArrowRight, text: 'El agente IA analiza la causa raíz y propone acciones correctivas' },
            { icon: Shield,      text: 'Tú apruebas — el sistema ejecuta, verifica y cierra el incidente' },
          ].map(({ icon: Icon, text }) => (
            <div key={text} className="flex items-start gap-2.5 text-xs text-slate-500">
              <Icon className="w-3.5 h-3.5 text-sky-500/60 shrink-0 mt-0.5" />
              <span>{text}</span>
            </div>
          ))}
        </div>

        {/* Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-8 shadow-2xl">
          <h2 className="text-slate-200 text-base font-semibold mb-6">Iniciar sesión</h2>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-slate-400 text-xs font-medium flex items-center gap-1.5">
                <Mail className="w-3.5 h-3.5" /> Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="bg-slate-950 border border-slate-700 rounded-lg px-3.5 py-2.5 text-slate-50 text-sm outline-none focus:border-sky-500/60 transition-colors placeholder-slate-600"
                placeholder="tu@email.com"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-slate-400 text-xs font-medium flex items-center gap-1.5">
                <Lock className="w-3.5 h-3.5" /> Contraseña
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="bg-slate-950 border border-slate-700 rounded-lg px-3.5 py-2.5 text-slate-50 text-sm outline-none focus:border-sky-500/60 transition-colors placeholder-slate-600"
                placeholder="••••••••"
              />
            </div>

            {error && (
              <div className="flex items-center gap-2 text-red-400 text-xs bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="flex items-center justify-center gap-2 bg-sky-600 hover:bg-sky-500 disabled:opacity-60 text-white rounded-lg py-2.5 text-sm font-semibold mt-1 transition-colors"
            >
              {loading ? 'Ingresando...' : (
                <>Iniciar sesión <ArrowRight className="w-4 h-4" /></>
              )}
            </button>
          </form>
        </div>

        {/* First-time hint */}
        <p className="text-center text-xs text-slate-600 mt-5">
          ¿Primera vez usando Sentinel?{' '}
          <Link to="/setup" className="text-sky-500 hover:text-sky-400 transition-colors">
            Ver guía de configuración
          </Link>
        </p>

        {/* Client branding */}
        <div className="flex items-center justify-center gap-2 mt-6 pt-5 border-t border-slate-800/60">
          <span className="text-[10px] text-slate-700 uppercase tracking-wider">Cliente</span>
          <div className="w-px h-3 bg-slate-800" />
          <img src="/softserve-logo.jpeg" alt="SoftServe" className="w-5 h-5 rounded-md object-cover opacity-80" />
          <a
            href="https://www.softserveinc.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-slate-500 hover:text-slate-400 transition-colors font-semibold"
          >
            SoftServe
          </a>
        </div>
      </div>
    </div>
  )
}

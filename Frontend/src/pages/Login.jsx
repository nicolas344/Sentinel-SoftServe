import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/useAuth'

export default function Login() {
  const { signIn } = useAuth()
  const navigate = useNavigate()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

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
    <div className="min-h-screen flex items-center justify-center bg-slate-950">
      <div className="bg-slate-800 p-10 rounded-xl w-full max-w-sm shadow-2xl">
        <h1 className="text-slate-50 text-3xl font-bold mb-1">Sentinel</h1>
        <p className="text-slate-400 text-sm mb-8">DevOps Incident Triage Copilot</p>

        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          <div className="flex flex-col gap-2">
            <label className="text-slate-300 text-sm font-medium">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="bg-slate-950 border border-slate-700 rounded-lg px-3.5 py-2.5 text-slate-50 text-sm outline-none"
              placeholder="tu@email.com"
            />
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-slate-300 text-sm font-medium">Contraseña</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="bg-slate-950 border border-slate-700 rounded-lg px-3.5 py-2.5 text-slate-50 text-sm outline-none"
              placeholder="••••••••"
            />
          </div>

          {error && <p className="text-red-400 text-sm">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="bg-sky-500 hover:bg-sky-400 disabled:opacity-60 text-white border-0 rounded-lg py-3 text-sm font-semibold cursor-pointer mt-2 transition-colors"
          >
            {loading ? 'Ingresando...' : 'Iniciar sesión'}
          </button>
        </form>

        <p className="text-center text-xs text-slate-500 mt-6">
          ¿Primera vez?{' '}
          <Link to="/setup" className="text-sky-400 hover:text-sky-300 transition-colors">
            Revisa la guía de configuración →
          </Link>
        </p>
      </div>
    </div>
  )
}

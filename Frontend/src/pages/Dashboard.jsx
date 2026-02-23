import { useAuth } from '../contexts/AuthContext'
import { useNavigate } from 'react-router-dom'

export default function Dashboard() {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()

  const handleSignOut = async () => {
    await signOut()
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50">
      <header className="flex items-center justify-between px-8 py-4 border-b border-slate-800 bg-slate-950">
        <h1 className="text-xl font-bold text-slate-50">Sentinel</h1>
        <div className="flex items-center gap-4">
          <span className="text-slate-400 text-sm">{user?.email}</span>
          <button
            onClick={handleSignOut}
            className="bg-transparent border border-slate-700 rounded-md px-3.5 py-1.5 text-slate-300 text-sm cursor-pointer"
          >
            Cerrar sesión
          </button>
        </div>
      </header>

      <main className="flex items-center justify-center h-[calc(100vh-65px)]">
        <p className="text-slate-600 text-sm">Dashboard de incidentes — próximamente</p>
      </main>
    </div>
  )
}

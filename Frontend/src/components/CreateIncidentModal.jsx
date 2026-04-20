import { useState, useEffect } from 'react'
import { supabase } from '../lib/supabase'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const SEVERITY_OPTIONS = [
    { value: 'critical', label: 'Crítico' },
    { value: 'high', label: 'Alto' },
    { value: 'medium', label: 'Medio' },
    { value: 'low', label: 'Bajo' },
]

export default function CreateIncidentModal({ onClose }) {
    const [title, setTitle] = useState('')
    const [target, setTarget] = useState('')
    const [severity, setSeverity] = useState('medium')
    const [sourceType, setSourceType] = useState('manual')
    const [description, setDescription] = useState('')
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)

    // Cerrar con tecla Escape
    useEffect(() => {
        const handleEsc = (e) => {
            if (e.key === 'Escape') onClose()
        }
        window.addEventListener('keydown', handleEsc)
        return () => window.removeEventListener('keydown', handleEsc)
    }, [onClose])

    const handleSubmit = async (e) => {
        e.preventDefault()
        setError(null)
        setLoading(true)

        try {
            // Obtener el JWT token del usuario autenticado
            const { data: { session } } = await supabase.auth.getSession()

            if (!session?.access_token) {
                setError('No se encontró sesión activa. Inicia sesión de nuevo.')
                setLoading(false)
                return
            }

            const res = await fetch(`${API_URL}/api/incidents/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${session.access_token}`,
                },
                body: JSON.stringify({
                    title: title.trim(),
                    target: target.trim(),
                    severity,
                    source_type: sourceType,
                    description: description.trim() || undefined,
                }),
            })

            if (!res.ok) {
                const data = await res.json().catch(() => null)
                throw new Error(data?.detail || `Error ${res.status}: No se pudo crear el incidente`)
            }

            // Éxito → cerrar modal (el realtime de Supabase actualiza la lista)
            onClose()
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
            onClick={onClose}
        >
            <div
                className="bg-slate-900 border border-slate-700 rounded-xl shadow-2xl w-full max-w-md mx-4 p-6"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div className="flex items-center justify-between mb-6">
                    <h2 className="text-lg font-semibold text-slate-100">Nuevo incidente</h2>
                    <button
                        onClick={onClose}
                        className="text-slate-500 hover:text-slate-300 text-xl leading-none transition-colors"
                        aria-label="Cerrar"
                    >
                        ×
                    </button>
                </div>

                {/* Formulario */}
                <form onSubmit={handleSubmit} className="flex flex-col gap-4">
                    {/* Título */}
                    <div className="flex flex-col gap-1.5">
                        <label className="text-sm font-medium text-slate-300">
                            Título <span className="text-red-400">*</span>
                        </label>
                        <input
                            type="text"
                            value={title}
                            onChange={(e) => setTitle(e.target.value)}
                            required
                            placeholder="Ej: Servicio nginx no responde"
                            className="bg-slate-950 border border-slate-700 rounded-lg px-3.5 py-2.5 text-sm text-slate-50 outline-none focus:border-blue-500 transition-colors placeholder:text-slate-600"
                        />
                    </div>

                    {/* Tipo de fuente */}
                    <div className="flex flex-col gap-1.5">
                        <label className="text-sm font-medium text-slate-300">
                            Tipo de recurso
                        </label>
                        <div className="flex gap-2">
                            {[
                                { value: 'manual',    label: 'Manual' },
                                { value: 'container', label: 'Contenedor' },
                                { value: 'database',  label: 'Base de datos' },
                            ].map((opt) => (
                                <button
                                    key={opt.value}
                                    type="button"
                                    onClick={() => setSourceType(opt.value)}
                                    className={`flex-1 px-3 py-2 rounded-lg text-xs font-medium transition-colors border ${
                                        sourceType === opt.value
                                            ? 'bg-blue-600 border-blue-500 text-white'
                                            : 'bg-slate-950 border-slate-700 text-slate-400 hover:border-slate-500'
                                    }`}
                                >
                                    {opt.label}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Recurso / Objetivo */}
                    <div className="flex flex-col gap-1.5">
                        <label className="text-sm font-medium text-slate-300">
                            Recurso <span className="text-red-400">*</span>
                        </label>
                        <input
                            type="text"
                            value={target}
                            onChange={(e) => setTarget(e.target.value)}
                            required
                            placeholder={
                                sourceType === 'database'
                                    ? 'Ej: postgres/app-db, mysql/orders'
                                    : 'Ej: nginx-prod, api-gateway'
                            }
                            className="bg-slate-950 border border-slate-700 rounded-lg px-3.5 py-2.5 text-sm text-slate-50 outline-none focus:border-blue-500 transition-colors placeholder:text-slate-600"
                        />
                    </div>

                    {/* Severidad */}
                    <div className="flex flex-col gap-1.5">
                        <label className="text-sm font-medium text-slate-300">
                            Severidad <span className="text-red-400">*</span>
                        </label>
                        <select
                            value={severity}
                            onChange={(e) => setSeverity(e.target.value)}
                            className="bg-slate-950 border border-slate-700 rounded-lg px-3.5 py-2.5 text-sm text-slate-50 outline-none focus:border-blue-500 transition-colors appearance-none cursor-pointer"
                        >
                            {SEVERITY_OPTIONS.map((opt) => (
                                <option key={opt.value} value={opt.value}>
                                    {opt.label}
                                </option>
                            ))}
                        </select>
                    </div>

                    {/* Descripción / Contexto */}
                    <div className="flex flex-col gap-1.5">
                        <label className="text-sm font-medium text-slate-300">
                            Descripción / Contexto{' '}
                            <span className="text-slate-600 text-xs">(opcional)</span>
                        </label>
                        <textarea
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            rows={4}
                            placeholder="Pega logs relevantes o describe lo que está ocurriendo..."
                            className="bg-slate-950 border border-slate-700 rounded-lg px-3.5 py-2.5 text-sm text-slate-50 outline-none focus:border-blue-500 transition-colors placeholder:text-slate-600 resize-none font-mono"
                        />
                    </div>

                    {/* Error */}
                    {error && (
                        <p className="text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                            {error}
                        </p>
                    )}

                    {/* Botones */}
                    <div className="flex items-center justify-end gap-3 mt-2">
                        <button
                            type="button"
                            onClick={onClose}
                            className="border border-slate-700 rounded-lg px-4 py-2 text-sm text-slate-400 hover:border-slate-500 hover:text-slate-300 transition-colors"
                        >
                            Cancelar
                        </button>
                        <button
                            type="submit"
                            disabled={loading}
                            className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg px-5 py-2 text-sm font-semibold transition-colors"
                        >
                            {loading ? 'Creando...' : 'Crear incidente'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    )
}

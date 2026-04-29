import { supabase } from '../lib/supabase'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export async function executeIncidentAction({ incidentId, command }) {
  const { data: { session } } = await supabase.auth.getSession()

  if (!session?.access_token) {
    throw new Error('No se encontro sesion activa. Inicia sesion de nuevo.')
  }

  const res = await fetch(`${API_URL}/api/execute-action`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${session.access_token}`,
    },
    body: JSON.stringify({
      incident_id: incidentId,
      command,
    }),
  })

  const data = await res.json().catch(() => null)

  if (!res.ok) {
    throw new Error(data?.detail || `Error ${res.status}: no se pudo ejecutar la accion`)
  }

  return data
}

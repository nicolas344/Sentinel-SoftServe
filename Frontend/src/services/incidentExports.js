import { jsPDF } from 'jspdf'
import { supabase } from '../lib/supabase'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function authHeaders() {
  const { data: { session } } = await supabase.auth.getSession()
  if (!session?.access_token) {
    throw new Error('No se encontro sesion activa. Inicia sesion de nuevo.')
  }
  return {
    Authorization: `Bearer ${session.access_token}`,
  }
}

export async function fetchPostMortem(incidentId) {
  const headers = await authHeaders()
  const res = await fetch(`${API_URL}/api/incidents/${incidentId}/post-mortem`, { headers })
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    throw new Error(data?.detail || `Error ${res.status}: no se pudo cargar el post-mortem`)
  }
  return data
}

export async function savePostMortem(incidentId, content) {
  const headers = await authHeaders()
  const res = await fetch(`${API_URL}/api/incidents/${incidentId}/post-mortem`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
    body: JSON.stringify({ content }),
  })
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    throw new Error(data?.detail || `Error ${res.status}: no se pudo guardar el post-mortem`)
  }
  return data
}

export async function fetchIncidentExport(incidentId, format) {
  const headers = await authHeaders()
  const res = await fetch(`${API_URL}/api/incidents/${incidentId}/export?format=${encodeURIComponent(format)}`, {
    headers,
  })

  if (!res.ok) {
    const data = await res.json().catch(() => null)
    throw new Error(data?.detail || `Error ${res.status}: no se pudo exportar el incidente`)
  }

  if (format === 'json') {
    return { content: JSON.stringify(await res.json(), null, 2), extension: 'json' }
  }
  return { content: await res.text(), extension: 'md' }
}

export function triggerTextDownload(content, filename, mimeType = 'text/plain;charset=utf-8') {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

export function exportPostMortemMarkdown(content, title) {
  const safeTitle = String(title || 'incident').replace(/[^a-zA-Z0-9_-]/g, '_')
  triggerTextDownload(content, `postmortem_${safeTitle}.md`, 'text/markdown;charset=utf-8')
}

export function exportPostMortemPdf(content, title) {
  const safeTitle = String(title || 'incident').replace(/[^a-zA-Z0-9_-]/g, '_')
  const doc = new jsPDF({ unit: 'pt', format: 'a4' })
  const margin = 40
  const pageWidth = doc.internal.pageSize.getWidth()
  const usableWidth = pageWidth - margin * 2

  doc.setFont('helvetica', 'normal')
  doc.setFontSize(10)
  const lines = doc.splitTextToSize(content || '', usableWidth)
  doc.text(lines, margin, margin + 10)
  doc.save(`postmortem_${safeTitle}.pdf`)
}

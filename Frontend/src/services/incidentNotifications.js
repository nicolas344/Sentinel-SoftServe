const SNOOZE_STORAGE_KEY = 'sentinel.notifications.snoozeUntil'
const NOTIFICATION_COOLDOWN_MS = 90 * 1000

const recentlyNotified = new Map()

const SUPPORTED_SEVERITIES = new Set(['high', 'critical'])

export function isNotificationsSupported() {
  return typeof window !== 'undefined' && 'Notification' in window
}

export function getNotificationPermission() {
  if (!isNotificationsSupported()) return 'unsupported'
  return Notification.permission
}

export async function requestNotificationPermission() {
  if (!isNotificationsSupported()) return 'unsupported'

  try {
    return await Notification.requestPermission()
  } catch {
    return Notification.permission || 'denied'
  }
}

function getSnoozeUntil() {
  if (typeof window === 'undefined') return 0
  const raw = window.localStorage.getItem(SNOOZE_STORAGE_KEY)
  const parsed = Number(raw)
  return Number.isFinite(parsed) ? parsed : 0
}

export function getSnoozeUntilTimestamp() {
  return getSnoozeUntil()
}

export function getSnoozeRemainingMs() {
  const remaining = getSnoozeUntil() - Date.now()
  return remaining > 0 ? remaining : 0
}

export function isSnoozed() {
  return getSnoozeRemainingMs() > 0
}

export function snoozeNotifications(minutes = 15) {
  if (typeof window === 'undefined') return 0

  const until = Date.now() + Math.max(1, minutes) * 60 * 1000
  window.localStorage.setItem(SNOOZE_STORAGE_KEY, String(until))
  return until
}

export function clearNotificationSnooze() {
  if (typeof window === 'undefined') return
  window.localStorage.removeItem(SNOOZE_STORAGE_KEY)
}

function formatTimestamp(value) {
  if (!value) return 'N/A'
  return new Date(value).toLocaleString('es-CO', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function shouldNotifyIncident(incident) {
  if (!incident) return false
  if (!SUPPORTED_SEVERITIES.has(String(incident.severity || '').toLowerCase())) return false
  if (incident.status === 'resolved') return false
  return true
}

function isUrgentSeverity(severity) {
  return SUPPORTED_SEVERITIES.has(String(severity || '').toLowerCase())
}

function isDuplicateInCooldown(incident) {
  const incidentId = incident?.id
  if (!incidentId) return true

  // Cooldown by incident id to avoid noisy UPDATE bursts from realtime.
  const now = Date.now()
  const previous = recentlyNotified.get(incidentId) || 0
  if (now - previous < NOTIFICATION_COOLDOWN_MS) return true

  recentlyNotified.set(incidentId, now)
  return false
}

function buildNotificationBody(incident) {
  const service = incident.container_name || incident.server_name || 'unknown-service'
  const eventType = incident.incident_type || incident.title || 'unknown'
  const timestamp = incident.created_at || incident.updated_at

  return [
    `Service: ${service}`,
    `Event: ${eventType}`,
    `Time: ${formatTimestamp(timestamp)}`,
  ].join('\n')
}

export function notifyIncident(incident, options = {}) {
  if (!isNotificationsSupported()) {
    console.debug('[Notifications] Browser does not support Notifications API')
    return false
  }
  if (Notification.permission !== 'granted') {
    console.debug(`[Notifications] Permission not granted (current: ${Notification.permission})`)
    return false
  }
  if (!shouldNotifyIncident(incident)) {
    console.debug(`[Notifications] Incident filtered: severity=${incident?.severity}, status=${incident?.status}`)
    return false
  }
  if (isSnoozed()) {
    console.debug('[Notifications] Notifications snoozed')
    return false
  }
  if (isDuplicateInCooldown(incident)) {
    console.debug(`[Notifications] Duplicate in cooldown: ${incident?.id}`)
    return false
  }

  const severity = String(incident.severity || '').toUpperCase()
  const targetUrl = options.targetUrl || '/'

  console.debug(`[Notifications] Sending ${severity} incident: ${incident?.id}`)

  const notification = new Notification(`Sentinel ${severity} incident`, {
    body: buildNotificationBody(incident),
    tag: `incident-${incident.id}`,
    renotify: false,
    // Keep both HIGH and CRITICAL visible so they are not missed on macOS.
    requireInteraction: isUrgentSeverity(incident.severity),
  })

  notification.onclick = () => {
    // Deep-link to dashboard detail so the on-call engineer lands on the exact incident.
    window.focus()
    window.location.href = targetUrl
    notification.close()
  }

  return true
}

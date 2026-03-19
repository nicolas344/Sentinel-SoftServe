import { useCallback, useMemo, useState } from 'react'
import {
  clearNotificationSnooze,
  getNotificationPermission,
  getSnoozeUntilTimestamp,
  isNotificationsSupported,
  isSnoozed,
  notifyIncident,
  requestNotificationPermission,
  snoozeNotifications,
} from '../services/incidentNotifications'

function formatSnoozeUntilLabel(timestamp) {
  if (!timestamp) return ''
  return new Date(timestamp).toLocaleTimeString('es-CO', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function useIncidentNotifications() {
  const [permission, setPermission] = useState(getNotificationPermission())
  const [snoozeUntilMs, setSnoozeUntilMs] = useState(getSnoozeUntilTimestamp())

  const refreshSnooze = useCallback(() => {
    setSnoozeUntilMs(getSnoozeUntilTimestamp())
  }, [])

  const askPermission = useCallback(async () => {
    const next = await requestNotificationPermission()
    setPermission(next)
    return next
  }, [])

  const snoozeForMinutes = useCallback((minutes = 15) => {
    snoozeNotifications(minutes)
    refreshSnooze()
  }, [refreshSnooze])

  const clearSnooze = useCallback(() => {
    clearNotificationSnooze()
    refreshSnooze()
  }, [refreshSnooze])

  const pushIncidentNotification = useCallback((incident) => {
    console.debug('[Hook] pushIncidentNotification called with:', {
      id: incident?.id,
      severity: incident?.severity,
      status: incident?.status,
      title: incident?.title,
    })
    const targetUrl = `${window.location.origin}/?incident=${incident.id}`
    return notifyIncident(incident, { targetUrl })
  }, [])

  const snoozed = isSnoozed()
  const snoozeUntilLabel = useMemo(() => {
    if (!snoozed) return ''
    return formatSnoozeUntilLabel(snoozeUntilMs)
  }, [snoozed, snoozeUntilMs])

  return {
    notificationsSupported: isNotificationsSupported(),
    notificationPermission: permission,
    askPermission,
    pushIncidentNotification,
    snoozed,
    snoozeUntilLabel,
    snoozeForMinutes,
    clearSnooze,
    refreshSnooze,
  }
}

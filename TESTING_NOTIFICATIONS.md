# Testing: Browser Notifications para Incidentes

## Configuración previa

### 1. Verificar que el backend esté corriendo
```bash
cd Backend
source env/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Verificar que el frontend esté corriendo
```bash
cd Frontend
npm run dev
# Abre http://localhost:5173
```

### 3. Verificar que Supabase está accesible
- Verifica que tienes las credenciales en Frontend/.env.local y Backend/.env correctamente configuradas
- Las notificaciones se actualizarán en realtime vía Supabase Realtime

---

## Método 1: POST directo (MÁS RÁPIDO para testing)

### Paso 1: Permitir notificaciones en el navegador
1. Abre http://localhost:5173 en tu navegador
2. Ya logeado en el dashboard, verás un botón azul "Activar alertas del navegador"
3. Haz click → acepta los permisos del navegador
4. El botón debe desaparecer y aparecer "Snooze 15m"

### Paso 2: Generar un incidente de prueba via POST
Abre una terminal y ejecuta:

```bash
curl -X POST http://localhost:8000/api/alerts \
  -H "Content-Type: application/json" \
  -d '{
    "status": "firing",
    "alerts": [
      {
        "status": "firing",
        "labels": {
          "alertname": "ContainerCrashed",
          "severity": "critical",
          "id": "/docker/test-container-12345abcdef",
          "instance": "cadvisor:8080"
        },
        "annotations": {
          "summary": "Test Critical Incident",
          "description": "Esto es un incidente de prueba para verificar notificaciones"
        },
        "startsAt": "2026-03-18T10:30:00Z"
      }
    ]
  }'
```

**Variables que puedes ajustar en el JSON:**
- `severity`: "critical" o "high" (solo estos dos generan notificaciones)
- `container_name`: cambia el valor en el label "id" (va a docker/VALOR)
- `summary`: el título del incidente

### Paso 3: Verificar la notificación
- **Si todo funciona:** en 1-2 segundos aparece una notificación del navegador
  - Título: "Sentinel CRITICAL incident" (o HIGH)
  - Body: Service, Event, Time
  - Click abre dashboard con el incidente seleccionado

- **Si algo falla:** abre Developer Tools (F12 → Console) y busca logs

---

## Método 2: Forzar caída de contenedor (MÁS REALISTA)

### Paso 1: Levanta Docker Compose completo
```bash
docker-compose up -d
# Espera 30s a que todos los servicios arranquen
```

### Paso 2: Listar contenedores
```bash
docker ps
```
Busca un contenedor que incluya "sentinel-" en el nombre (ej: sentinel-chromadb, sentinel-loki, etc.)

### Paso 3: Mata un contenedor
```bash
docker stop sentinel-chromadb  # o cualquier otro
```

### Paso 4: Espera la detección
- Prometheus scrape cada 5s y evalúa reglas cada 5s
- Alertmanager espera 5s antes de enviar (para agrupar)
- **Total: ~15-20 segundos hasta que llega la alerta**

### Paso 5: Verifica la notificación
- Notificación debe aparecer en el navegador automáticamente
- El incidente debe estar en la lista del dashboard

---

## Debugging en Developer Tools

### F12 → Console
Busca estos logs útiles:

```javascript
// Si ves esto, las notificaciones están activas
"Notificaciones soportadas: true"

// Si ves esto, algún incidente llegó pero no se notificó (probablemente snooze o severidad)
"Incidente X notificado: false"
```

### F12 → Application → Local Storage
- **Clave:** `sentinel.notifications.snoozeUntil`
- Si existe y tiene un timestamp en el futuro, estamos en snooze
- Para limpiar snooze manualmente: haz click en el botón "Reactivar" del header

---

## Test Checklist

- [ ] Permisos de notificador: botón "Activar alertas" clickeable
- [ ] Generar incidente: corre el curl del Método 1
- [ ] Notificación llega: ves popup en 1-2s
- [ ] Contenido correcto: Service, Event, Time visibles
- [ ] Click funciona: abre dashboard con incidente seleccionado
- [ ] Snooze funciona: después de snooze, nueva notificación no llega (prueba otro POST)
- [ ] Reactivar: después de click "Reactivar", notificaciones vuelven

---

## Troubleshooting

### "No veo notificación pero el incidente llegó al dashboard"
**Causa:** Probablemente permisos denegados
**Solución:** 
1. Revisa el header del dashboard → ¿Ves botón azul "Activar alertas"?
2. Si no ves nada, quizás ya tiene permisos: F12 → Application → Check notification permission

### "Recibo notificación copia de la anterior (duplicada)"
**Causa:** Cooldown de 90s no aplicado (posible bug)
**Solución:** Espera 90+ segundos entre POST para asegurar dedupe

### "Incidente llegó pero severidad es LOW o MEDIUM"
**Causa:** Solo notificamos high y critical
**Solución:** Usa severity: "critical" o "high" en el POST

### "Hash de incidente diferente cada vez"
**Causa:** Esperado, PostgreSQL genera nueva UUID
**Verdad:** Cada POST crea nuevo incidente, así que tag de notificación es único

---

## Variantes de test avanzado

### Test de HIGH severity
```bash
curl -X POST http://localhost:8000/api/alerts \
  -H "Content-Type: application/json" \
  -d '{
    "status": "firing",
    "alerts": [{
      "status": "firing",
      "labels": {
        "alertname": "ContainerOOMKilled",
        "severity": "high",
        "id": "/docker/my-app-service",
        "instance": "cadvisor:8080"
      },
      "annotations": {
        "summary": "High: OOM en servicio"
      },
      "startsAt": "2026-03-18T10:35:00Z"
    }]
  }'
```

### Test de "resolved" (no debería notificar)
```bash
curl -X POST http://localhost:8000/api/alerts \
  -H "Content-Type: application/json" \
  -d '{
    "status": "resolved",
    "alerts": [{
      "status": "resolved",
      "labels": {
        "alertname": "ContainerCrashed",
        "severity": "critical",
        "id": "/docker/fixed-service"
      },
      "annotations": {
        "summary": "Resolved"
      },
      "startsAt": "2026-03-18T10:00:00Z",
      "endsAt": "2026-03-18T10:40:00Z"
    }]
  }'
```
No debería generar notificación (status resolved siempre se excluye)

### Test de snooze
1. Corre dos POST con 5 segundos de diferencia
2. Primera notificación: sí llega
3. Segunda notificación: no llega (cooldown de 90s)
4. Haz click "Snooze 15m" en el header
5. Corre tercer POST: no llega (snooze activo)
6. Haz click "Reactivar"
7. Espera 90s y corre cuarto POST: sí llega (se limpió el cooldown anterior)

---

## Estado esperado después de test exitoso

**Dashboard:**
- [ ] Lista de incidentes actualiza en realtime
- [ ] Incident count en header (críticos activos)
- [ ] Panel detalle se abre con incidente al clickear notificación

**Header:**
- [ ] Botón snooze presente e interactivo
- [ ] Label de "Snooze hasta HH:MM" cuando está activo
- [ ] Botón "Reactivar" limpia snooze

**Logs en Console:**
- [ ] Sin errores de notificación
- [ ] Sin crashes de React

---

## Limpiar data de test

```bash
# Para limpiar todos los incidentes de test y empezar de cero:
# 1. Abre Supabase dashboard
# 2. Tabla "incidents" → delete all rows
# 3. O vacía el localStorage en el navegador: F12 → Application → Local Storage → Delete

# Para resetnear el cooldown:
window.localStorage.removeItem('sentinel.notifications.snoozeUntil')
```

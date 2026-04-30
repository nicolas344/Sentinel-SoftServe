-- Agrega soporte para aprobacion y ejecucion controlada de soluciones en incidentes.
ALTER TABLE incidents
  ADD COLUMN IF NOT EXISTS proposed_action TEXT,
  ADD COLUMN IF NOT EXISTS action_result TEXT,
  ADD COLUMN IF NOT EXISTS action_error TEXT,
  ADD COLUMN IF NOT EXISTS executed_at TIMESTAMPTZ;

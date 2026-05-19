-- Campos para post-mortem editable/exportable por incidente.
ALTER TABLE incidents
  ADD COLUMN IF NOT EXISTS post_mortem_md TEXT,
  ADD COLUMN IF NOT EXISTS post_mortem_updated_at TIMESTAMPTZ;

-- Migration 004: Add 'kubernetes' to container_runtime allowed values
-- Extends the check constraint to support the KubernetesAgent

ALTER TABLE incidents
  DROP CONSTRAINT IF EXISTS incidents_container_runtime_check;

ALTER TABLE incidents
  ADD CONSTRAINT incidents_container_runtime_check
  CHECK (container_runtime IN ('docker', 'podman', 'kubernetes'));

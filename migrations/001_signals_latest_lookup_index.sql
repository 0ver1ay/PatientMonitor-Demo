-- PatientMonitor demo migration
-- Speeds up live latest-value and history range lookups.
-- Safe for production/demo: CONCURRENTLY does not block writes.
-- Must run with autocommit (not inside an explicit transaction).

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_signals_bed_signal_time_desc
ON public.signals (bed_id, signal_id, signals_date_time DESC NULLS LAST);

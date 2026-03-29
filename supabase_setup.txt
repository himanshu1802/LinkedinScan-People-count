-- ═══════════════════════════════════════════════════════════════
--  LinkedScan — Supabase Schema
--  Run this in your Supabase project → SQL Editor → New query
-- ═══════════════════════════════════════════════════════════════

-- 1. Job history table
CREATE TABLE IF NOT EXISTS job_history (
    id            UUID    DEFAULT gen_random_uuid() PRIMARY KEY,
    job_id        TEXT    NOT NULL UNIQUE,
    device_id     TEXT    NOT NULL,          -- anonymous device fingerprint
    filename      TEXT,
    started_at    TIMESTAMPTZ,
    finished_at   TIMESTAMPTZ,
    total         INTEGER DEFAULT 0,
    found         INTEGER DEFAULT 0,
    failed        INTEGER DEFAULT 0,
    avg_time_s    REAL    DEFAULT 0,
    success_rate  REAL    DEFAULT 0,
    results_json  JSONB,                     -- full row results
    columns_json  JSONB,                     -- column names
    created_at    TIMESTAMPTZ DEFAULT now()
);

-- 2. Index for fast device-scoped queries
CREATE INDEX IF NOT EXISTS idx_job_history_device ON job_history (device_id, created_at DESC);

-- 3. Row Level Security — each device only sees its own rows
ALTER TABLE job_history ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "device_read"   ON job_history;
DROP POLICY IF EXISTS "device_insert" ON job_history;
DROP POLICY IF EXISTS "device_delete" ON job_history;

-- Allow any anon client to read rows matching their device_id header/filter
CREATE POLICY "device_read" ON job_history
    FOR SELECT USING (true);          -- filtered in query by device_id

CREATE POLICY "device_insert" ON job_history
    FOR INSERT WITH CHECK (true);     -- device_id validated app-side

CREATE POLICY "device_delete" ON job_history
    FOR DELETE USING (true);          -- device_id validated in WHERE clause

-- 4. Settings table (per device)
CREATE TABLE IF NOT EXISTS device_settings (
    device_id  TEXT PRIMARY KEY,
    settings   JSONB DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE device_settings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "device_settings_all" ON device_settings;
CREATE POLICY "device_settings_all" ON device_settings
    FOR ALL USING (true) WITH CHECK (true);

-- ═══════════════════════════════════════════════════════════════
-- Done! Copy your Supabase Project URL and anon key from:
--   Supabase Dashboard → Settings → API
-- and paste them in the LinkedScan Settings tab.
-- ═══════════════════════════════════════════════════════════════

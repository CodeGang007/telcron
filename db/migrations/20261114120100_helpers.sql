-- Shared helper functions used by generated schema migrations. Hand-written.

-- migrate:up

-- Keeps updated_at current on every UPDATE.
CREATE OR REPLACE FUNCTION telcron_set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END $$;

-- Append-only guard. Trigger arguments = columns that MAY change on UPDATE (none ⇒ insert-only).
-- DELETE is always refused, except inside a privileged purge (account deletion / retention job),
-- which sets the transaction-local flag telcron.allow_purge = 'on'.
CREATE OR REPLACE FUNCTION telcron_guard_immutable() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    allowed text[] := coalesce(TG_ARGV, '{}'::text[]);   -- TG_ARGV is NULL (not empty) when no args
BEGIN
    IF current_setting('telcron.allow_purge', true) = 'on' THEN
        RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
    END IF;
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'telcron: % is append-only — DELETE is not allowed', TG_TABLE_NAME
            USING ERRCODE = 'TC001';
    END IF;
    IF (to_jsonb(OLD) - allowed) IS DISTINCT FROM (to_jsonb(NEW) - allowed) THEN
        RAISE EXCEPTION 'telcron: % is append-only — only % may change', TG_TABLE_NAME,
            coalesce(array_to_string(allowed, ', '), 'nothing') USING ERRCODE = 'TC001';
    END IF;
    RETURN NEW;
END $$;

-- Creates a DEFAULT partition plus monthly range partitions [p_start, p_start + p_months).
-- Run monthly (cron/scheduler) to stay ahead: SELECT telcron_create_monthly_partitions('audit_log', date_trunc('month', now())::date, 3);
CREATE OR REPLACE FUNCTION telcron_create_monthly_partitions(p_table text, p_start date, p_months int)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    d date;
BEGIN
    EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF %I DEFAULT', p_table || '_default', p_table);
    FOR i IN 0 .. p_months - 1 LOOP
        d := (date_trunc('month', p_start) + make_interval(months => i))::date;
        EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF %I FOR VALUES FROM (%L) TO (%L)',
                       p_table || '_' || to_char(d, 'YYYY_MM'), p_table,
                       d::timestamp AT TIME ZONE 'UTC', (d + interval '1 month')::timestamp AT TIME ZONE 'UTC');
    END LOOP;
END $$;

-- Reads a typed setting from app_settings with a fallback.
CREATE OR REPLACE FUNCTION telcron_setting_int(p_key text, p_default bigint) RETURNS bigint
LANGUAGE plpgsql STABLE AS $$
BEGIN
    RETURN coalesce((SELECT (value #>> '{}')::bigint FROM app_settings WHERE key = p_key), p_default);
END $$;

-- migrate:down
DROP FUNCTION IF EXISTS telcron_setting_int(text, bigint);
DROP FUNCTION IF EXISTS telcron_create_monthly_partitions(text, date, int);
DROP FUNCTION IF EXISTS telcron_guard_immutable();
DROP FUNCTION IF EXISTS telcron_set_updated_at();

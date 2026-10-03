-- The three runtime login roles of `RRA-017` `FR-270`, for the local and staging compose stacks.
--
-- Mounted into `/docker-entrypoint-initdb.d/`, so PostgreSQL runs it once, as the bootstrap
-- superuser, when a stack's data volume is first initialised. For a volume that already exists,
-- run it once by hand:
--
--   docker compose -f docker-compose.local.yml exec -T postgres \
--     psql -U khepri -d khepri -f - < ops/local/khepri-runtime-roles.sql
--
-- It only creates the roles and sets their passwords. The migration (`20261002_0036`) grants
-- them everything they hold, and creates any it finds missing, without a password. These
-- passwords are not secrets, exactly as the stacks' `khepri:khepri` is not: each matches the
-- default URL in `khepri.local.config` and the staging compose file's secret for that role.
-- `tests/test_rra017_connection_model.py` holds the three together.
--
-- Idempotent: safe to run again. Every attribute is the one the migration's own check requires.

DO $$
DECLARE
  role_name text;
BEGIN
  FOREACH role_name IN ARRAY ARRAY['khepri_app', 'khepri_worker', 'khepri_sweep'] LOOP
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = role_name) THEN
      EXECUTE format(
        'CREATE ROLE %I LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB NOINHERIT',
        role_name
      );
    END IF;
    EXECUTE format('ALTER ROLE %I PASSWORD %L', role_name, role_name);
  END LOOP;
END $$;

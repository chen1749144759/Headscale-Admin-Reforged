-- Make the signed OTA policy authoritative and replay resistant.
-- Existing v1/v2 releases are retained for audit history but disabled because
-- their signatures did not bind the action or a monotonic policy revision.

ALTER TABLE client_releases ADD COLUMN IF NOT EXISTS policy_revision BIGINT;

UPDATE client_releases
SET policy_revision = id
WHERE policy_revision IS NULL OR policy_revision <= 0;

UPDATE client_releases
SET platform = COALESCE(NULLIF(LOWER(BTRIM(platform)), ''), 'windows-amd64'),
    update_type = CASE
        WHEN LOWER(BTRIM(COALESCE(update_type, ''))) IN ('suggested', 'forced', 'clear')
            THEN LOWER(BTRIM(update_type))
        ELSE 'suggested'
    END,
    download_url = COALESCE(download_url, ''),
    sha256 = COALESCE(LOWER(sha256), ''),
    signature = COALESCE(signature, ''),
    file_size = COALESCE(file_size, 0),
    enabled = COALESCE(enabled, FALSE);

ALTER TABLE client_releases ALTER COLUMN policy_revision SET NOT NULL;
ALTER TABLE client_releases ALTER COLUMN platform SET DEFAULT 'windows-amd64';
ALTER TABLE client_releases ALTER COLUMN platform SET NOT NULL;
ALTER TABLE client_releases ALTER COLUMN update_type SET DEFAULT 'suggested';
ALTER TABLE client_releases ALTER COLUMN update_type SET NOT NULL;
ALTER TABLE client_releases ALTER COLUMN download_url SET DEFAULT '';
ALTER TABLE client_releases ALTER COLUMN download_url SET NOT NULL;
ALTER TABLE client_releases ALTER COLUMN sha256 SET DEFAULT '';
ALTER TABLE client_releases ALTER COLUMN sha256 SET NOT NULL;
ALTER TABLE client_releases ALTER COLUMN signature SET DEFAULT '';
ALTER TABLE client_releases ALTER COLUMN signature SET NOT NULL;
ALTER TABLE client_releases ALTER COLUMN file_size SET DEFAULT 0;
ALTER TABLE client_releases ALTER COLUMN file_size SET NOT NULL;
ALTER TABLE client_releases ALTER COLUMN enabled SET DEFAULT TRUE;
ALTER TABLE client_releases ALTER COLUMN enabled SET NOT NULL;

UPDATE client_releases
SET enabled = FALSE,
    updated_at = NOW()
WHERE enabled = TRUE
  AND COALESCE(signature, '') !~ '^v3\.[A-Za-z0-9+/]{86}==$';

DO $$
DECLARE
    constraint_name TEXT;
BEGIN
    FOR constraint_name IN
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'client_releases'::regclass
          AND contype = 'c'
          AND pg_get_constraintdef(oid) ILIKE '%update_type%'
    LOOP
        EXECUTE format('ALTER TABLE client_releases DROP CONSTRAINT %I', constraint_name);
    END LOOP;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'client_releases'::regclass
          AND conname = 'client_releases_policy_revision_check'
    ) THEN
        ALTER TABLE client_releases
            ADD CONSTRAINT client_releases_policy_revision_check
            CHECK (policy_revision > 0 AND policy_revision <= 9007199254740991);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'client_releases'::regclass
          AND conname = 'client_releases_update_type_v3_check'
    ) THEN
        ALTER TABLE client_releases
            ADD CONSTRAINT client_releases_update_type_v3_check
            CHECK (update_type IN ('suggested', 'forced', 'clear'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'client_releases'::regclass
          AND conname = 'client_releases_artifact_v3_check'
    ) THEN
        ALTER TABLE client_releases
            ADD CONSTRAINT client_releases_artifact_v3_check
            CHECK (
                NOT enabled
                OR (update_type = 'clear' AND download_url = '' AND sha256 = '' AND file_size = 0)
                OR (update_type IN ('suggested', 'forced') AND download_url <> '' AND sha256 <> '' AND file_size > 0)
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'client_releases'::regclass
          AND conname = 'client_releases_signature_v3_check'
    ) THEN
        ALTER TABLE client_releases
            ADD CONSTRAINT client_releases_signature_v3_check
            CHECK (NOT enabled OR signature ~ '^v3\.[A-Za-z0-9+/]{86}==$');
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS ux_client_releases_platform_policy_revision
    ON client_releases (LOWER(platform), policy_revision);

CREATE INDEX IF NOT EXISTS idx_client_releases_policy_revision
    ON client_releases (policy_revision DESC);

CREATE OR REPLACE FUNCTION scaleforge_reject_client_release_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'client release policies are append-only; publish a higher revision instead'
        USING ERRCODE = '55000';
END;
$$;

DROP TRIGGER IF EXISTS client_releases_append_only ON client_releases;
CREATE TRIGGER client_releases_append_only
BEFORE UPDATE OR DELETE ON client_releases
FOR EACH ROW EXECUTE FUNCTION scaleforge_reject_client_release_mutation();

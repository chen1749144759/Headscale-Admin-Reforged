-- Keep 001 immutable: it may already be recorded by checksum in production.
-- This follow-up migration normalizes columns added to legacy tables by 001.

ALTER TABLE flow_summaries
    ALTER COLUMN machine_name SET DEFAULT '',
    ALTER COLUMN group_name SET DEFAULT '',
    ALTER COLUMN connection_count SET DEFAULT 0,
    ALTER COLUMN state SET DEFAULT '',
    ALTER COLUMN process_name SET DEFAULT '';

UPDATE flow_summaries
SET machine_name = COALESCE(machine_name, ''),
    group_name = COALESCE(group_name, ''),
    connection_count = COALESCE(connection_count, 0),
    state = COALESCE(state, ''),
    process_name = COALESCE(process_name, '')
WHERE machine_name IS NULL
   OR group_name IS NULL
   OR connection_count IS NULL
   OR state IS NULL
   OR process_name IS NULL;

ALTER TABLE flow_summaries
    ALTER COLUMN machine_name SET NOT NULL,
    ALTER COLUMN group_name SET NOT NULL,
    ALTER COLUMN connection_count SET NOT NULL,
    ALTER COLUMN state SET NOT NULL,
    ALTER COLUMN process_name SET NOT NULL;

ALTER TABLE client_releases
    ALTER COLUMN sha256 SET DEFAULT '',
    ALTER COLUMN signature SET DEFAULT '',
    ALTER COLUMN file_size SET DEFAULT 0;

-- Unsigned legacy releases remain visible to managers but are excluded from OTA
-- delivery by the application-level signature validator.
UPDATE client_releases
SET sha256 = COALESCE(sha256, ''),
    signature = COALESCE(signature, ''),
    file_size = CASE WHEN file_size IS NULL OR file_size < 0 THEN 0 ELSE file_size END
WHERE sha256 IS NULL
   OR signature IS NULL
   OR file_size IS NULL
   OR file_size < 0;

ALTER TABLE client_releases
    ALTER COLUMN sha256 SET NOT NULL,
    ALTER COLUMN signature SET NOT NULL,
    ALTER COLUMN file_size SET NOT NULL;

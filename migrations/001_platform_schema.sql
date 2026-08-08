-- ScaleForge owns all management, telemetry, policy, audit and release tables.
-- Headscale owns accounts, users and nodes referenced below.

CREATE TABLE IF NOT EXISTS acl (
    id BIGSERIAL PRIMARY KEY,
    acl TEXT,
    account_id BIGINT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS log (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT,
    content TEXT NOT NULL,
    action TEXT NOT NULL DEFAULT 'operation',
    resource TEXT NOT NULL DEFAULT '',
    result TEXT NOT NULL DEFAULT 'success',
    source_ip TEXT NOT NULL DEFAULT '',
    request_id TEXT NOT NULL DEFAULT '',
    user_agent TEXT NOT NULL DEFAULT '',
    before_state JSONB,
    after_state JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS client_policies (
    id BIGSERIAL PRIMARY KEY,
    scope TEXT NOT NULL,
    group_id BIGINT,
    group_name TEXT NOT NULL DEFAULT '',
    machine_id BIGINT,
    machine_name TEXT NOT NULL DEFAULT '',
    rate_up_mbps DOUBLE PRECISION,
    rate_down_mbps DOUBLE PRECISION,
    monthly_quota_gb DOUBLE PRECISION,
    exceed_action TEXT NOT NULL DEFAULT 'throttle',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    priority INTEGER NOT NULL DEFAULT 100,
    created_by_account_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    remark TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS client_policy_states (
    id BIGSERIAL PRIMARY KEY,
    machine_id BIGINT,
    machine_name TEXT NOT NULL DEFAULT '',
    policy_revision TEXT NOT NULL DEFAULT '',
    matched_policy_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    applied BOOLEAN NOT NULL DEFAULT FALSE,
    effective_policy JSONB NOT NULL DEFAULT '{}'::jsonb,
    error TEXT NOT NULL DEFAULT '',
    applied_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS traffic_samples (
    id BIGSERIAL PRIMARY KEY,
    machine_id BIGINT,
    machine_name TEXT NOT NULL DEFAULT '',
    group_id BIGINT,
    group_name TEXT NOT NULL DEFAULT '',
    rx_bytes_total BIGINT NOT NULL DEFAULT 0,
    tx_bytes_total BIGINT NOT NULL DEFAULT 0,
    rx_bytes_delta BIGINT NOT NULL DEFAULT 0,
    tx_bytes_delta BIGINT NOT NULL DEFAULT 0,
    rx_rate_bps DOUBLE PRECISION NOT NULL DEFAULT 0,
    tx_rate_bps DOUBLE PRECISION NOT NULL DEFAULT 0,
    derp BOOLEAN NOT NULL DEFAULT FALSE,
    endpoint_type TEXT NOT NULL DEFAULT '',
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS traffic_hourly (
    id BIGSERIAL PRIMARY KEY,
    bucket_start TIMESTAMPTZ NOT NULL,
    machine_id BIGINT,
    group_id BIGINT,
    rx_bytes BIGINT NOT NULL DEFAULT 0,
    tx_bytes BIGINT NOT NULL DEFAULT 0,
    peak_rx_rate_bps DOUBLE PRECISION NOT NULL DEFAULT 0,
    peak_tx_rate_bps DOUBLE PRECISION NOT NULL DEFAULT 0,
    UNIQUE(bucket_start, machine_id)
);

CREATE TABLE IF NOT EXISTS traffic_daily (
    id BIGSERIAL PRIMARY KEY,
    bucket_date DATE NOT NULL,
    machine_id BIGINT,
    group_id BIGINT,
    rx_bytes BIGINT NOT NULL DEFAULT 0,
    tx_bytes BIGINT NOT NULL DEFAULT 0,
    UNIQUE(bucket_date, machine_id)
);

CREATE TABLE IF NOT EXISTS node_ip_observations (
    id BIGSERIAL PRIMARY KEY,
    machine_id BIGINT,
    machine_name TEXT NOT NULL DEFAULT '',
    group_id BIGINT,
    group_name TEXT NOT NULL DEFAULT '',
    ip TEXT NOT NULL,
    country TEXT NOT NULL DEFAULT '',
    region TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL DEFAULT '',
    asn TEXT NOT NULL DEFAULT '',
    isp TEXT NOT NULL DEFAULT '',
    risk_flags JSONB NOT NULL DEFAULT '[]'::jsonb,
    first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    seen_count INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS flow_summaries (
    id BIGSERIAL PRIMARY KEY,
    machine_id BIGINT,
    machine_name TEXT NOT NULL DEFAULT '',
    group_id BIGINT,
    group_name TEXT NOT NULL DEFAULT '',
    window_start TIMESTAMPTZ NOT NULL,
    window_seconds INTEGER NOT NULL DEFAULT 60,
    dst_ip TEXT NOT NULL DEFAULT '',
    dst_port INTEGER,
    protocol TEXT NOT NULL DEFAULT '',
    direction TEXT NOT NULL DEFAULT '',
    bytes BIGINT NOT NULL DEFAULT 0,
    packets BIGINT NOT NULL DEFAULT 0,
    connection_count INTEGER NOT NULL DEFAULT 0,
    state TEXT NOT NULL DEFAULT '',
    process_id INTEGER,
    process_name TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS security_events (
    id BIGSERIAL PRIMARY KEY,
    level TEXT NOT NULL DEFAULT 'info',
    event_type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    group_id BIGINT,
    group_name TEXT NOT NULL DEFAULT '',
    machine_id BIGINT,
    machine_name TEXT NOT NULL DEFAULT '',
    ip TEXT NOT NULL DEFAULT '',
    country TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL DEFAULT '',
    asn TEXT NOT NULL DEFAULT '',
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'open',
    handled_by_account_id BIGINT,
    handled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS trusted_networks (
    id BIGSERIAL PRIMARY KEY,
    kind TEXT NOT NULL,
    value TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_by_account_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS risk_rules (
    id BIGSERIAL PRIMARY KEY,
    rule_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    level TEXT NOT NULL DEFAULT 'medium',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS client_releases (
    id BIGSERIAL PRIMARY KEY,
    version TEXT NOT NULL,
    platform TEXT NOT NULL DEFAULT 'windows-amd64',
    update_type TEXT NOT NULL DEFAULT 'suggested',
    title TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    download_url TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    signature TEXT NOT NULL DEFAULT '',
    file_size BIGINT NOT NULL DEFAULT 0,
    release_notes TEXT NOT NULL DEFAULT '',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_by_account_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Upgrade prior unversioned schemas before legacy ownership columns are removed.
ALTER TABLE acl ADD COLUMN IF NOT EXISTS account_id BIGINT;
ALTER TABLE acl ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE log ADD COLUMN IF NOT EXISTS account_id BIGINT;
ALTER TABLE log ADD COLUMN IF NOT EXISTS action TEXT NOT NULL DEFAULT 'operation';
ALTER TABLE log ADD COLUMN IF NOT EXISTS resource TEXT NOT NULL DEFAULT '';
ALTER TABLE log ADD COLUMN IF NOT EXISTS result TEXT NOT NULL DEFAULT 'success';
ALTER TABLE log ADD COLUMN IF NOT EXISTS source_ip TEXT NOT NULL DEFAULT '';
ALTER TABLE log ADD COLUMN IF NOT EXISTS request_id TEXT NOT NULL DEFAULT '';
ALTER TABLE log ADD COLUMN IF NOT EXISTS user_agent TEXT NOT NULL DEFAULT '';
ALTER TABLE log ADD COLUMN IF NOT EXISTS before_state JSONB;
ALTER TABLE log ADD COLUMN IF NOT EXISTS after_state JSONB;

ALTER TABLE client_policies ADD COLUMN IF NOT EXISTS created_by_account_id BIGINT;
ALTER TABLE client_policy_states ADD COLUMN IF NOT EXISTS policy_revision TEXT NOT NULL DEFAULT '';
ALTER TABLE client_policy_states ADD COLUMN IF NOT EXISTS matched_policy_ids JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE flow_summaries ADD COLUMN IF NOT EXISTS machine_name TEXT;
ALTER TABLE flow_summaries ADD COLUMN IF NOT EXISTS group_name TEXT;
ALTER TABLE flow_summaries ADD COLUMN IF NOT EXISTS connection_count INTEGER DEFAULT 0;
ALTER TABLE flow_summaries ADD COLUMN IF NOT EXISTS state TEXT;
ALTER TABLE flow_summaries ADD COLUMN IF NOT EXISTS process_id INTEGER;
ALTER TABLE flow_summaries ADD COLUMN IF NOT EXISTS process_name TEXT;
ALTER TABLE security_events ADD COLUMN IF NOT EXISTS handled_by_account_id BIGINT;
ALTER TABLE trusted_networks ADD COLUMN IF NOT EXISTS created_by_account_id BIGINT;
ALTER TABLE client_releases ADD COLUMN IF NOT EXISTS sha256 TEXT;
ALTER TABLE client_releases ADD COLUMN IF NOT EXISTS signature TEXT;
ALTER TABLE client_releases ADD COLUMN IF NOT EXISTS file_size BIGINT;
ALTER TABLE client_releases ADD COLUMN IF NOT EXISTS created_by_account_id BIGINT;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='acl' AND column_name='user_id') THEN
        EXECUTE 'UPDATE acl x SET account_id=a.id FROM accounts a WHERE x.account_id IS NULL AND a.user_id=x.user_id';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='log' AND column_name='user_id') THEN
        EXECUTE 'UPDATE log x SET account_id=a.id FROM accounts a WHERE x.account_id IS NULL AND a.user_id=x.user_id';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='client_policies' AND column_name='created_by') THEN
        EXECUTE 'UPDATE client_policies x SET created_by_account_id=a.id FROM accounts a WHERE x.created_by_account_id IS NULL AND a.user_id=x.created_by';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='security_events' AND column_name='handled_by') THEN
        EXECUTE 'UPDATE security_events x SET handled_by_account_id=a.id FROM accounts a WHERE x.handled_by_account_id IS NULL AND a.user_id=x.handled_by';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='trusted_networks' AND column_name='created_by') THEN
        EXECUTE 'UPDATE trusted_networks x SET created_by_account_id=a.id FROM accounts a WHERE x.created_by_account_id IS NULL AND a.user_id=x.created_by';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='client_releases' AND column_name='created_by') THEN
        EXECUTE 'UPDATE client_releases x SET created_by_account_id=a.id FROM accounts a WHERE x.created_by_account_id IS NULL AND a.user_id=x.created_by';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema='public'
          AND table_name='client_policy_states'
          AND column_name='policy_id'
    ) THEN
        EXECUTE $backfill$
            UPDATE client_policy_states
            SET matched_policy_ids = CASE
                WHEN COALESCE(matched_policy_ids, '[]'::jsonb) @> jsonb_build_array(policy_id)
                    THEN COALESCE(matched_policy_ids, '[]'::jsonb)
                ELSE COALESCE(matched_policy_ids, '[]'::jsonb) || jsonb_build_array(policy_id)
            END
            WHERE policy_id IS NOT NULL
        $backfill$;
    END IF;
END $$;

ALTER TABLE acl DROP COLUMN IF EXISTS user_id CASCADE;
ALTER TABLE log DROP COLUMN IF EXISTS user_id CASCADE;
ALTER TABLE client_policies DROP COLUMN IF EXISTS created_by CASCADE;
ALTER TABLE client_policy_states DROP COLUMN IF EXISTS policy_id CASCADE;
ALTER TABLE security_events DROP COLUMN IF EXISTS handled_by CASCADE;
ALTER TABLE trusted_networks DROP COLUMN IF EXISTS created_by CASCADE;
ALTER TABLE client_releases DROP COLUMN IF EXISTS created_by CASCADE;

UPDATE acl x SET account_id=NULL WHERE account_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM accounts a WHERE a.id=x.account_id);
UPDATE log x SET account_id=NULL WHERE account_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM accounts a WHERE a.id=x.account_id);
UPDATE client_policies x SET created_by_account_id=NULL WHERE created_by_account_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM accounts a WHERE a.id=x.created_by_account_id);
UPDATE security_events x SET handled_by_account_id=NULL WHERE handled_by_account_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM accounts a WHERE a.id=x.handled_by_account_id);
UPDATE trusted_networks x SET created_by_account_id=NULL WHERE created_by_account_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM accounts a WHERE a.id=x.created_by_account_id);
UPDATE client_releases x SET created_by_account_id=NULL WHERE created_by_account_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM accounts a WHERE a.id=x.created_by_account_id);

-- Current node ownership becomes the authoritative snapshot after an upgrade.
UPDATE traffic_samples x SET group_id=n.user_id FROM nodes n WHERE x.machine_id=n.id AND x.group_id IS DISTINCT FROM n.user_id;
UPDATE traffic_hourly x SET group_id=n.user_id FROM nodes n WHERE x.machine_id=n.id AND x.group_id IS DISTINCT FROM n.user_id;
UPDATE traffic_daily x SET group_id=n.user_id FROM nodes n WHERE x.machine_id=n.id AND x.group_id IS DISTINCT FROM n.user_id;
UPDATE node_ip_observations x SET group_id=n.user_id FROM nodes n WHERE x.machine_id=n.id AND x.group_id IS DISTINCT FROM n.user_id;
UPDATE flow_summaries x SET group_id=n.user_id FROM nodes n WHERE x.machine_id=n.id AND x.group_id IS DISTINCT FROM n.user_id;
UPDATE security_events x SET group_id=n.user_id FROM nodes n WHERE x.machine_id=n.id AND x.group_id IS DISTINCT FROM n.user_id;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_acl_account') THEN
        ALTER TABLE acl ADD CONSTRAINT fk_acl_account FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_log_account') THEN
        ALTER TABLE log ADD CONSTRAINT fk_log_account FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_client_policies_creator') THEN
        ALTER TABLE client_policies ADD CONSTRAINT fk_client_policies_creator FOREIGN KEY(created_by_account_id) REFERENCES accounts(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_security_events_handler') THEN
        ALTER TABLE security_events ADD CONSTRAINT fk_security_events_handler FOREIGN KEY(handled_by_account_id) REFERENCES accounts(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_trusted_networks_creator') THEN
        ALTER TABLE trusted_networks ADD CONSTRAINT fk_trusted_networks_creator FOREIGN KEY(created_by_account_id) REFERENCES accounts(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_client_releases_creator') THEN
        ALTER TABLE client_releases ADD CONSTRAINT fk_client_releases_creator FOREIGN KEY(created_by_account_id) REFERENCES accounts(id) ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_acl_account_id ON acl(account_id);
CREATE INDEX IF NOT EXISTS idx_log_account_id ON log(account_id);
CREATE INDEX IF NOT EXISTS idx_log_created_at ON log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_client_policies_scope ON client_policies(scope);
CREATE INDEX IF NOT EXISTS idx_client_policies_group_id ON client_policies(group_id);
CREATE INDEX IF NOT EXISTS idx_client_policies_machine_id ON client_policies(machine_id);
DELETE FROM client_policy_states stale
USING client_policy_states keep
WHERE stale.machine_id IS NOT NULL
  AND stale.machine_id=keep.machine_id
  AND stale.id < keep.id;
CREATE UNIQUE INDEX IF NOT EXISTS idx_client_policy_states_machine_id ON client_policy_states(machine_id) WHERE machine_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_traffic_samples_machine_time ON traffic_samples(machine_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_traffic_samples_group_time ON traffic_samples(group_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_node_ip_observations_machine ON node_ip_observations(machine_id);
CREATE INDEX IF NOT EXISTS idx_flow_summaries_machine_window ON flow_summaries(machine_id, window_start DESC);
CREATE INDEX IF NOT EXISTS idx_security_events_status ON security_events(status);
CREATE INDEX IF NOT EXISTS idx_security_events_level ON security_events(level);
CREATE INDEX IF NOT EXISTS idx_security_events_created_at ON security_events(created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_trusted_networks_kind_value ON trusted_networks(kind, value);
CREATE INDEX IF NOT EXISTS idx_client_releases_enabled_platform ON client_releases(enabled, platform);
CREATE INDEX IF NOT EXISTS idx_client_releases_created_at ON client_releases(created_at DESC);

-- Historical telemetry and audit records must survive deletion or reassignment
-- of the current Headscale user or node. Fresh installs already omit these
-- ownership foreign keys; this migration makes upgraded databases equivalent.

ALTER TABLE IF EXISTS client_policies
    DROP CONSTRAINT IF EXISTS client_policies_group_id_fkey,
    DROP CONSTRAINT IF EXISTS client_policies_machine_id_fkey;
ALTER TABLE IF EXISTS client_policy_states
    DROP CONSTRAINT IF EXISTS client_policy_states_machine_id_fkey;
ALTER TABLE IF EXISTS traffic_samples
    DROP CONSTRAINT IF EXISTS traffic_samples_machine_id_fkey,
    DROP CONSTRAINT IF EXISTS traffic_samples_group_id_fkey;
ALTER TABLE IF EXISTS traffic_hourly
    DROP CONSTRAINT IF EXISTS traffic_hourly_machine_id_fkey,
    DROP CONSTRAINT IF EXISTS traffic_hourly_group_id_fkey;
ALTER TABLE IF EXISTS traffic_daily
    DROP CONSTRAINT IF EXISTS traffic_daily_machine_id_fkey,
    DROP CONSTRAINT IF EXISTS traffic_daily_group_id_fkey;
ALTER TABLE IF EXISTS node_ip_observations
    DROP CONSTRAINT IF EXISTS node_ip_observations_machine_id_fkey,
    DROP CONSTRAINT IF EXISTS node_ip_observations_group_id_fkey;
ALTER TABLE IF EXISTS flow_summaries
    DROP CONSTRAINT IF EXISTS flow_summaries_machine_id_fkey,
    DROP CONSTRAINT IF EXISTS flow_summaries_group_id_fkey;
ALTER TABLE IF EXISTS security_events
    DROP CONSTRAINT IF EXISTS security_events_machine_id_fkey,
    DROP CONSTRAINT IF EXISTS security_events_group_id_fkey;

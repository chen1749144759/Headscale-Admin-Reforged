-- Business users are accounts. Headscale nodes remain protocol records and
-- business groups are reusable classifications stored in account_groups.

UPDATE traffic_samples x
SET machine_id = a.id,
    machine_name = a.username,
    group_id = a.group_id,
    group_name = COALESCE(g.name, '')
FROM nodes n
JOIN accounts a ON a.user_id = n.user_id
LEFT JOIN account_groups g ON g.id = a.group_id AND g.deleted_at IS NULL
WHERE x.machine_id = n.id;

UPDATE traffic_hourly x
SET machine_id = a.id,
    group_id = a.group_id
FROM nodes n
JOIN accounts a ON a.user_id = n.user_id
WHERE x.machine_id = n.id;

UPDATE traffic_daily x
SET machine_id = a.id,
    group_id = a.group_id
FROM nodes n
JOIN accounts a ON a.user_id = n.user_id
WHERE x.machine_id = n.id;

UPDATE node_ip_observations x
SET machine_id = a.id,
    machine_name = a.username,
    group_id = a.group_id,
    group_name = COALESCE(g.name, '')
FROM nodes n
JOIN accounts a ON a.user_id = n.user_id
LEFT JOIN account_groups g ON g.id = a.group_id AND g.deleted_at IS NULL
WHERE x.machine_id = n.id;

UPDATE flow_summaries x
SET machine_id = a.id,
    machine_name = a.username,
    group_id = a.group_id,
    group_name = COALESCE(g.name, '')
FROM nodes n
JOIN accounts a ON a.user_id = n.user_id
LEFT JOIN account_groups g ON g.id = a.group_id AND g.deleted_at IS NULL
WHERE x.machine_id = n.id;

UPDATE security_events x
SET machine_id = a.id,
    machine_name = a.username,
    group_id = a.group_id,
    group_name = COALESCE(g.name, '')
FROM nodes n
JOIN accounts a ON a.user_id = n.user_id
LEFT JOIN account_groups g ON g.id = a.group_id AND g.deleted_at IS NULL
WHERE x.machine_id = n.id;

UPDATE client_policy_states x
SET machine_id = a.id,
    machine_name = a.username
FROM nodes n
JOIN accounts a ON a.user_id = n.user_id
WHERE x.machine_id = n.id;

UPDATE client_policies x
SET machine_id = a.id,
    machine_name = a.username,
    updated_at = NOW()
FROM nodes n
JOIN accounts a ON a.user_id = n.user_id
WHERE x.scope = 'machine'
  AND x.machine_id = n.id;

UPDATE client_policies x
SET group_id = g.id,
    group_name = g.name,
    updated_at = NOW()
FROM users u
JOIN account_groups g ON LOWER(g.name) = LOWER(u.name) AND g.deleted_at IS NULL
WHERE x.scope = 'group'
  AND x.group_id = u.id;

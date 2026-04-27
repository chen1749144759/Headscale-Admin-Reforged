#!/bin/bash
set -e

export PGPASSWORD="HsAdmin@2026PG"

echo "=== Step 1: Drop and recreate headscale_admin database ==="
# Connect as postgres user via local socket (no password required for local connections)
psql -h 127.0.0.1 -p 15432 -U headscale_admin -d headscale_admin << 'SQL'
-- Drop all tables owned by headscale_admin
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO headscale_admin;
GRANT ALL ON SCHEMA public TO public;
SQL

echo "=== Step 2: Update headscale config to database ACL mode ==="
python3 << 'PYEOF'
import yaml

config = {
    'server_url': 'http://127.0.0.1:18557',
    'listen_addr': '0.0.0.0:18557',
    'grpc_listen_addr': '127.0.0.1:50444',
    'grpc_allow_insecure': False,
    'noise': {
        'private_key_path': '/var/lib/headscale-custom/noise_private.key'
    },
    'prefixes': {
        'v4': '100.64.0.0/10',
        'v6': 'fd7a:115c:a1e0::/48',
        'allocation': 'sequential'
    },
    'derp': {
        'server': {
            'enabled': True,
            'region_id': 999,
            'region_code': 'headscale',
            'region_name': 'Headscale Embedded DERP',
            'stun_listen_addr': '0.0.0.0:3478',
            'verify_clients': False,
            'private_key_path': '/var/lib/headscale-custom/derp.key'
        },
        'urls': [
            'https://controlplane.tailscale.com/derpmap/default'
        ]
    },
    'database': {
        'type': 'postgres',
        'postgres': {
            'host': '127.0.0.1',
            'port': 15432,
            'name': 'headscale_admin',
            'user': 'headscale_admin',
            'pass': 'HsAdmin@2026PG',
            'ssl': False,
            'max_open_conns': 10,
            'max_idle_conns': 10,
            'conn_max_idle_time_secs': 3600
        }
    },
    'dns': {
        'base_domain': 'hs.admin.pro',
        'override_local_dns': True,
        'nameservers': {
            'global': ['1.1.1.1', '8.8.8.8']
        }
    },
    'log': {
        'level': 'info',
        'format': 'text'
    },
    'policy': {
        'mode': 'database'
    }
}

with open('/etc/headscale-custom/config.yaml', 'w') as f:
    yaml.dump(config, f, default_flow_style=False, sort_keys=False)

print('Config updated successfully')
PYEOF

echo "=== Step 3: Restart headscale-custom ==="
systemctl restart headscale-custom
sleep 4

echo "=== Step 4: Verify ==="
curl -s http://127.0.0.1:18557/health
echo ""
echo "Done!"

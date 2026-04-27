#!/usr/bin/env python3
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
            'verify_clients': False
        },
        'urls': [
            'https://controlplane.tailscale.com/derpmap/default'
        ]
    },
    'database': {
        'type': 'sqlite',
        'sqlite': {
            'path': '/var/lib/headscale-custom/db.sqlite',
            'write_ahead_log': True
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
        'mode': 'file',
        'path': '/etc/headscale-custom/acl.hujson'
    }
}

with open('/etc/headscale-custom/config.yaml', 'w') as f:
    yaml.dump(config, f, default_flow_style=False, sort_keys=False)

print('Config written successfully')

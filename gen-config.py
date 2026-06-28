#!/usr/bin/env python3
import os
import yaml


def env_bool(name, default):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in ('0', 'false', 'no', 'off')


def env_list(name, default):
    raw = os.environ.get(name)
    if not raw:
        return default
    return [item.strip() for item in raw.replace(';', ',').split(',') if item.strip()]


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
        'magic_dns': env_bool('HEADSCALE_MAGIC_DNS', True),
        'base_domain': os.environ.get('HEADSCALE_DNS_DOMAIN', 'hs.admin.pro'),
        'override_local_dns': env_bool('HEADSCALE_DNS_OVERRIDE_LOCAL', True),
        'nameservers': {
            'global': env_list('HEADSCALE_DNS_GLOBAL', ['1.1.1.1', '8.8.8.8'])
        },
        'search_domains': env_list('HEADSCALE_DNS_SEARCH_DOMAINS', [])
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

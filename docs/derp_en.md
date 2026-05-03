# DERP Relay Server Configuration Guide

English | [中文](derp.md)

## What is DERP

DERP (Designated Encrypted Relay for Packets) is Tailscale's NAT traversal relay protocol. When two nodes cannot establish a direct (P2P) connection, traffic is forwarded through a DERP relay server. DERP consists of two components:

- **STUN** (UDP) — Helps nodes discover their public addresses and attempt hole-punching for direct connections
- **DERP Relay** (TCP/TLS) — When hole-punching fails, acts as an encrypted relay to forward traffic

Headscale-Admin-Reforged includes a standalone DERP server (`derper`) by default, deployed via Docker Compose with zero manual certificate or domain configuration.

## Architecture

```
                    Tailscale Client A
                          │
              ┌───────────┼───────────┐
              │ STUN (UDP)│           │ DERP Relay (TLS)
              ▼           │           ▼
     ┌────────────────────┴────────────────────┐
     │              hs-derper container         │
     │  STUN :3478/udp    DERP Relay :3479/tcp │
     └─────────────────────────────────────────┘
              │ STUN (UDP)            │ DERP Relay (TLS)
              ▼                       ▼
                    Tailscale Client B
```

The DERP server does **not communicate directly** with Headscale. Headscale tells clients where to find the DERP server via the DERP Map (`derp.yaml`), and clients connect on their own.

## Default Configuration

| Setting | .env Variable | Default | Description |
|---------|--------------|---------|-------------|
| DERP Domain/IP | `DERP_DOMAIN` | Same as `HEADSCALE_SERVER_URL` | Public address clients use to reach DERP |
| STUN Port | `DERP_STUN_PORT` | `3478` | UDP, for NAT traversal |
| DERP Port | `DERP_HTTP_PORT` | `3479` | TCP, DERP relay (TLS encrypted) |

## Zero-Config Deployment

When `DERP_DOMAIN` is set in `.env`, Docker Compose automatically:

1. **Renders the DERP Map** from `derp.yaml.tmpl` with your domain and ports
2. **Generates a self-signed TLS certificate** (10-year validity) if none exists
3. **Starts derper** with the self-signed cert for STUN + DERP Relay
4. **Configures client trust** via `insecurefortests: true` in the DERP Map

No manual steps required.

## .env Configuration

```bash
# DERP relay — must be your public IP or domain
DERP_DOMAIN=203.0.113.1

# STUN port (UDP)
DERP_STUN_PORT=3478

# DERP Relay port (TCP)
DERP_HTTP_PORT=3479
```

## Firewall / NAT Port Mapping

Ensure these ports are open in your firewall and NAT:

| Port | Protocol | Purpose |
|------|----------|---------|
| `DERP_STUN_PORT` | UDP | STUN hole-punching |
| `DERP_HTTP_PORT` | **TCP** | DERP relay (must be TCP, not UDP) |

## Verification

```bash
# Check container status
docker compose ps

# Check derper logs (should show "with TLS")
docker logs hs-derper

# Client-side netcheck
tailscale netcheck

# Ping between nodes
tailscale ping <peer-ip>
```

## Security

All traffic relayed through DERP is end-to-end encrypted with WireGuard. The DERP server cannot decrypt or inspect any content. Your DERP server address is only distributed to registered nodes in your Tailnet via the private DERP Map.

## Troubleshooting

See the [Chinese version](derp.md#故障排查) for detailed troubleshooting steps.

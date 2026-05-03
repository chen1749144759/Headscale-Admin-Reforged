# <img src="icon.ico" width="32" height="32" alt="ScaleForge Icon" /> ScaleForge

[![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Vue 3](https://img.shields.io/badge/Vue-3.x-4FC08D?logo=vuedotjs&logoColor=white)](https://vuejs.org/)
[![Element Plus](https://img.shields.io/badge/Element%20Plus-2.x-409EFF?logo=element&logoColor=white)](https://element-plus.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](#quick-start-docker-compose)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)

> **A completely rewritten web management panel for [headscale](https://github.com/juanfont/headscale).**

[English](#) | [中文](../README.md) | [Deutsch](README_de.md) | [Français](README_fr.md) | [Русский](README_ru.md)

---

## About

**ScaleForge** is a **complete rewrite** of [arounyf/Headscale-Admin-Pro](https://github.com/arounyf/Headscale-Admin-Pro) v4.0.0.

The original project was a monolithic application built with Flask + Jinja2. This project has been entirely rebuilt with a modern **frontend-backend separated** architecture: FastAPI serves the REST API on the backend, while Vue 3 powers a SPA on the frontend — all wrapped in a brand-new dark glassmorphism UI.

### Credits & Origin

This project is forked from [arounyf/Headscale-Admin-Pro](https://github.com/arounyf/Headscale-Admin-Pro) tag 4.0.0. Special thanks to **arounyf** for the original work.

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.13 + FastAPI + Uvicorn |
| Frontend | Vue 3 + Vite + Element Plus + Pinia + Vue Router 4 |
| Authentication | JWT + native bcrypt (Python 3.13 + bcrypt 5.x compatible) |
| Database | PostgreSQL 16 (Docker) / SQLite (local dev) |
| Headscale | [Headscale-Admin-AE](https://github.com/chen1749144759/Headscale-Admin-AE) (enhanced edition) |
| DERP Relay | Standalone [derper](https://pkg.go.dev/tailscale.com/cmd/derper) with auto-generated self-signed TLS cert |

### Architecture

```
                              ┌─────────────────────────────────┐
                              │           Browser               │
                              └──────────────┬──────────────────┘
                                             │ :80
                                             ▼
                              ┌─────────────────────────────────┐
                              │     Nginx (SPA + Reverse Proxy) │
                              │  ┌───────────┬────────────────┐ │
                              │  │ Vue3 SPA  │ /api/* → :5175 │ │
                              │  │  static   │ /hs/*  → :8080 │ │
                              │  └───────────┴────────┬───────┘ │
                              └───────────────────────┼─────────┘
                                        ┌─────────────┤
                                        ▼             ▼
                    ┌──────────────────────┐   ┌───────────────────┐
                    │  FastAPI (port 5175) │   │  Headscale AE     │
                    │   Admin Backend      │   │   (port 8080)     │
                    └─────────┬────────────┘   └────────┬──────────┘
                              │                         │
                              ▼                         ▼
                    ┌──────────────────────────────────────────────┐
                    │          PostgreSQL 16 (shared database)     │
                    └──────────────────────────────────────────────┘

    ┌─────────────────────────────────────┐
    │   derper (standalone DERP relay)    │
    │   STUN :3478/udp  DERP :3479/tcp   │
    └─────────────────────────────────────┘
```

## Features

- **Dashboard** — Real-time CPU/memory/traffic monitoring with smooth trend charts, node statistics
- **Group Management** — Headscale user namespace management, node quota, ACL rule templates
- **Node Management** — List, search, filter, rename, delete, tag management (forcedTags)
- **Route Management** — Subnet routes, approve/revoke, autoApprovers editor, Exit Nodes
- **ACL Rule Editor** — HuJSON support, formatting, line numbers, database mode sync
- **Preauthkey Management** — Create/delete, one-click copy
- **DERP Relay** — Private standalone DERP server with auto TLS, zero-config deployment
- **System Settings** — Connection config, API key, registration policy, security lock
- **Operation Logs** — Paginated audit trail with human-readable names
- **Health Monitoring** — Real-time headscale connection status in header bar

## Screenshots

| Dashboard | User Management |
|:---:|:---:|
| ![Dashboard](screenshots/首页.png) | ![User Management](screenshots/用户.png) |

| Group Management | ACL Rules |
|:---:|:---:|
| ![Group Management](screenshots/分组.png) | ![ACL Rules](screenshots/ACL.png) |

| Route Management | Preauthkeys |
|:---:|:---:|
| ![Route Management](screenshots/路由.png) | ![Preauthkeys](screenshots/预认证.png) |

---

## Quick Start (Docker Compose)

The simplest deployment — one command brings up all services (PostgreSQL + Headscale AE + DERP Relay + Admin Backend + Nginx).

### Prerequisites

- Linux server (Ubuntu 22/24 recommended)
- Docker + Docker Compose

```bash
# Install Docker if needed
curl -fsSL https://get.docker.com | sh
```

### Step 1: Download

```bash
mkdir -p ~/headscale-admin && cd ~/headscale-admin

# Download docker-compose.yml and template files
for f in docker-compose.yml config.yaml.tmpl derp.yaml.tmpl entrypoint.sh .env.example; do
  curl -fsSL -o "$f" \
    "https://raw.githubusercontent.com/chen1749144759/ScaleForge/main/docker/$f"
done
chmod +x entrypoint.sh
```

### Step 2: Configure .env

```bash
cp .env.example .env
```

Edit `.env` and set **at minimum**:

```bash
# REQUIRED — Your server's public IP or domain
HEADSCALE_SERVER_URL=http://YOUR_PUBLIC_IP:8080

# REQUIRED — DERP relay public address (usually same as above)
DERP_DOMAIN=YOUR_PUBLIC_IP
```

> **Important**: `HEADSCALE_SERVER_URL` must be reachable by Tailscale clients. If you change `HS_PORT`, update the URL port accordingly.

### Step 3: Launch

```bash
docker compose up -d
```

First launch automatically pulls images, generates TLS certificates for DERP, and starts all services in the correct order with health checks.

### Step 4: Verify

```bash
docker compose ps   # All should show healthy/Up
```

| Address | Purpose |
|---------|---------|
| `http://YOUR_IP` | Admin panel |
| `http://YOUR_IP:8080` | Headscale API (client connection) |

### Step 5: Create Admin

Open `http://YOUR_IP` in your browser. **The first registered user becomes admin** (registration closes after).

### Firewall Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 80 | TCP | Web admin panel |
| 8080 | TCP | Headscale API + Noise protocol |
| 3478 | UDP | STUN (NAT traversal) |
| 3479 | TCP | DERP relay (TLS encrypted) |

### Common Commands

```bash
# Stop all services
docker compose down

# Update images and restart
docker compose pull && docker compose up -d

# View logs
docker compose logs -f --tail=50

# Database backup
docker exec hs-postgres pg_dump -U headscale_admin headscale_admin > backup.sql

# Manually create API Key
docker exec hs-headscale headscale apikey create
```

### Data Persistence

All data is persisted via Docker Volumes — `docker compose down` won't lose data:

- `postgres-data` — Database
- `headscale-data` — Headscale runtime data + API Key
- `derper-certs` — DERP server TLS certificates

To fully reset: `docker compose down -v` (**data is irrecoverable**).

---

## Advanced Deployment

For single-container Docker deployment, bare-metal installation, and detailed environment variable reference, see the [Chinese README](../README.md#方式二docker-单容器部署).

## DERP Relay Configuration

The standalone DERP relay server is automatically configured during deployment. For custom port mapping, troubleshooting, and security hardening, see:

- [DERP Configuration Guide (Chinese)](derp.md)
- [DERP Configuration Guide (English)](derp_en.md)

## Client Connection

After deployment, install Tailscale on your devices and point to your Headscale:

```bash
# Linux
tailscale up --login-server=http://YOUR_PUBLIC_IP:8080

# Windows / macOS
# Set Login Server in Tailscale client settings
```

## Related Projects

| Project | Description |
|---------|-------------|
| [Headscale-Admin-AE](https://github.com/chen1749144759/Headscale-Admin-AE) | Enhanced headscale binary required by this project |
| [Headscale-Admin-Pro](https://github.com/arounyf/Headscale-Admin-Pro) | Original project by arounyf |
| [headscale](https://github.com/juanfont/headscale) | Official headscale project |

## Roadmap

- [x] Docker Compose one-click deployment
- [x] Standalone DERP relay with auto TLS
- [x] Real-time traffic trend charts
- [ ] Dark/light mode toggle
- [ ] Multi-language i18n support
- [ ] OIDC / SSO integration
- [ ] Mobile responsive optimization

## Contributing

Issues and Pull Requests are welcome. Before submitting a PR:

1. Ensure the frontend builds without errors (`npm run build`)
2. Keep backend API backward compatible
3. Write clear commit messages describing the changes

## License

This project is open-sourced under the [MIT License](../LICENSE).

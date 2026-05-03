# <img src="icon.ico" width="32" height="32" alt="ScaleForge Icon" /> ScaleForge

[![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Vue 3](https://img.shields.io/badge/Vue-3.x-4FC08D?logo=vuedotjs&logoColor=white)](https://vuejs.org/)
[![Element Plus](https://img.shields.io/badge/Element%20Plus-2.x-409EFF?logo=element&logoColor=white)](https://element-plus.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](#schnellstart-docker-compose)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)

> **Ein komplett neu geschriebenes Web-Verwaltungspanel für [headscale](https://github.com/juanfont/headscale).**

[English](README_en.md) | [中文](../README.md) | [Deutsch](#) | [Français](README_fr.md) | [Русский](README_ru.md)

---

## Über das Projekt

**ScaleForge** ist eine **vollständige Neuentwicklung** von [arounyf/Headscale-Admin-Pro](https://github.com/arounyf/Headscale-Admin-Pro) v4.0.0.

Das ursprüngliche Projekt war eine monolithische Anwendung mit Flask + Jinja2. Dieses Projekt wurde komplett mit einer modernen **Frontend-Backend-Trennung** neu aufgebaut: FastAPI stellt die REST-API im Backend bereit, während Vue 3 eine SPA im Frontend antreibt — eingebettet in ein brandneues Dark-Glassmorphism-UI.

### Danksagung & Ursprung

Dieses Projekt ist ein Fork von [arounyf/Headscale-Admin-Pro](https://github.com/arounyf/Headscale-Admin-Pro) Tag 4.0.0. Besonderer Dank an **arounyf** für die ursprüngliche Arbeit.

## Technologie-Stack

| Ebene | Technologie |
|-------|-------------|
| Backend | Python 3.13 + FastAPI + Uvicorn |
| Frontend | Vue 3 + Vite + Element Plus + Pinia + Vue Router 4 |
| Authentifizierung | JWT + natives bcrypt (Python 3.13 + bcrypt 5.x kompatibel) |
| Datenbank | PostgreSQL 16 (Docker) / SQLite (lokale Entwicklung) |
| Headscale | [Headscale-Admin-AE](https://github.com/chen1749144759/Headscale-Admin-AE) (erweiterte Edition) |
| DERP-Relay | Eigenständiger [derper](https://pkg.go.dev/tailscale.com/cmd/derper) mit automatisch generiertem selbstsigniertem TLS-Zertifikat |

### Architektur

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
                    │  FastAPI (Port 5175) │   │  Headscale AE     │
                    │   Admin-Backend      │   │   (Port 8080)     │
                    └─────────┬────────────┘   └────────┬──────────┘
                              │                         │
                              ▼                         ▼
                    ┌──────────────────────────────────────────────┐
                    │          PostgreSQL 16 (gemeinsame Datenbank) │
                    └──────────────────────────────────────────────┘

    ┌─────────────────────────────────────┐
    │   derper (eigenständiges DERP-Relay)│
    │   STUN :3478/udp  DERP :3479/tcp   │
    └─────────────────────────────────────┘
```

## Funktionen

- **Dashboard** — Echtzeit-Überwachung von CPU/Arbeitsspeicher/Datenverkehr mit fließenden Trenddiagrammen, Knotenstatistiken
- **Gruppenverwaltung** — Headscale-Benutzer-Namespace-Verwaltung, Knotenkontingent, ACL-Regelvorlagen
- **Knotenverwaltung** — Auflisten, suchen, filtern, umbenennen, löschen, Tag-Verwaltung (forcedTags)
- **Routenverwaltung** — Subnetz-Routen, genehmigen/widerrufen, autoApprovers-Editor, Exit-Nodes
- **ACL-Regel-Editor** — HuJSON-Unterstützung, Formatierung, Zeilennummern, Datenbankmodus-Synchronisation
- **Preauthkey-Verwaltung** — Erstellen/löschen, Ein-Klick-Kopieren
- **DERP-Relay** — Privater eigenständiger DERP-Server mit automatischem TLS, Zero-Config-Bereitstellung
- **Systemeinstellungen** — Verbindungskonfiguration, API-Key, Registrierungsrichtlinie, Sicherheitssperre
- **Betriebsprotokolle** — Seitengestützter Prüfpfad mit lesbaren Namen
- **Gesundheitsüberwachung** — Echtzeit-Headscale-Verbindungsstatus in der Kopfleiste

## Screenshots

| Dashboard | Benutzerverwaltung |
|:---:|:---:|
| ![Dashboard](screenshots/首页.png) | ![Benutzerverwaltung](screenshots/用户.png) |

| Gruppenverwaltung | ACL-Regeln |
|:---:|:---:|
| ![Gruppenverwaltung](screenshots/分组.png) | ![ACL-Regeln](screenshots/ACL.png) |

| Routenverwaltung | Preauthkeys |
|:---:|:---:|
| ![Routenverwaltung](screenshots/路由.png) | ![Preauthkeys](screenshots/预认证.png) |

---

## Schnellstart (Docker Compose)

Die einfachste Bereitstellung — ein Befehl startet alle Dienste (PostgreSQL + Headscale AE + DERP-Relay + Admin-Backend + Nginx).

### Voraussetzungen

- Linux-Server (Ubuntu 22/24 empfohlen)
- Docker + Docker Compose

```bash
# Docker installieren, falls nötig
curl -fsSL https://get.docker.com | sh
```

### Schritt 1: Herunterladen

```bash
mkdir -p ~/headscale-admin && cd ~/headscale-admin

# docker-compose.yml und Vorlagendateien herunterladen
for f in docker-compose.yml config.yaml.tmpl derp.yaml.tmpl entrypoint.sh .env.example; do
  curl -fsSL -o "$f" \
    "https://raw.githubusercontent.com/chen1749144759/ScaleForge/main/docker/$f"
done
chmod +x entrypoint.sh
```

### Schritt 2: .env konfigurieren

```bash
cp .env.example .env
```

Bearbeiten Sie `.env` und setzen Sie **mindestens**:

```bash
# ERFORDERLICH — Öffentliche IP oder Domain Ihres Servers
HEADSCALE_SERVER_URL=http://IHRE_OEFFENTLICHE_IP:8080

# ERFORDERLICH — Öffentliche Adresse des DERP-Relays (normalerweise identisch)
DERP_DOMAIN=IHRE_OEFFENTLICHE_IP
```

> **Wichtig**: `HEADSCALE_SERVER_URL` muss für Tailscale-Clients erreichbar sein. Wenn Sie `HS_PORT` ändern, passen Sie den URL-Port entsprechend an.

### Schritt 3: Starten

```bash
docker compose up -d
```

Der erste Start lädt automatisch Images, generiert TLS-Zertifikate für DERP und startet alle Dienste in der richtigen Reihenfolge mit Health-Checks.

### Schritt 4: Überprüfen

```bash
docker compose ps   # Alle sollten healthy/Up anzeigen
```

| Adresse | Zweck |
|---------|-------|
| `http://IHRE_IP` | Admin-Panel |
| `http://IHRE_IP:8080` | Headscale API (Client-Verbindung) |

### Schritt 5: Administrator erstellen

Öffnen Sie `http://IHRE_IP` im Browser. **Der erste registrierte Benutzer wird automatisch Administrator** (die Registrierung wird danach geschlossen).

### Firewall-Ports

| Port | Protokoll | Zweck |
|------|-----------|-------|
| 80 | TCP | Web-Admin-Panel |
| 8080 | TCP | Headscale API + Noise-Protokoll |
| 3478 | UDP | STUN (NAT-Traversal) |
| 3479 | TCP | DERP-Relay (TLS-verschlüsselt) |

### Häufige Befehle

```bash
# Alle Dienste stoppen
docker compose down

# Images aktualisieren und neu starten
docker compose pull && docker compose up -d

# Logs anzeigen
docker compose logs -f --tail=50

# Datenbank-Backup
docker exec hs-postgres pg_dump -U headscale_admin headscale_admin > backup.sql

# API-Key manuell erstellen
docker exec hs-headscale headscale apikey create
```

### Datenpersistenz

Alle Daten werden über Docker-Volumes persistiert — `docker compose down` führt nicht zu Datenverlust:

- `postgres-data` — Datenbank
- `headscale-data` — Headscale-Laufzeitdaten + API-Key
- `derper-certs` — DERP-Server-TLS-Zertifikate

Zum vollständigen Zurücksetzen: `docker compose down -v` (**Daten sind unwiederbringlich**).

---

## Erweiterte Bereitstellung

Für Einzelcontainer-Docker-Bereitstellung, Bare-Metal-Installation und detaillierte Umgebungsvariablen-Referenz siehe das [chinesische README](../README.md#方式二docker-单容器部署).

## DERP-Relay-Konfiguration

Der eigenständige DERP-Relay-Server wird während der Bereitstellung automatisch konfiguriert. Für benutzerdefiniertes Port-Mapping, Fehlerbehebung und Sicherheitshärtung siehe:

- [DERP-Konfigurationsanleitung (Chinesisch)](derp.md)
- [DERP Configuration Guide (Englisch)](derp_en.md)

## Client-Verbindung

Installieren Sie nach der Bereitstellung Tailscale auf Ihren Geräten und verweisen Sie auf Ihr Headscale:

```bash
# Linux
tailscale up --login-server=http://IHRE_OEFFENTLICHE_IP:8080

# Windows / macOS
# Setzen Sie den Login-Server in den Tailscale-Client-Einstellungen
```

## Verwandte Projekte

| Projekt | Beschreibung |
|---------|--------------|
| [Headscale-Admin-AE](https://github.com/chen1749144759/Headscale-Admin-AE) | Erweiterte Headscale-Binärdatei, die von diesem Projekt benötigt wird |
| [Headscale-Admin-Pro](https://github.com/arounyf/Headscale-Admin-Pro) | Originalprojekt von arounyf |
| [headscale](https://github.com/juanfont/headscale) | Offizielles headscale-Projekt |

## Roadmap

- [x] Docker Compose Ein-Klick-Bereitstellung
- [x] Eigenständiges DERP-Relay mit automatischem TLS
- [x] Echtzeit-Verkehrstrend-Diagramme
- [ ] Dark/Light-Modus-Umschaltung
- [ ] Mehrsprachige i18n-Unterstützung
- [ ] OIDC / SSO-Integration
- [ ] Mobile responsive Optimierung

## Mitwirken

Issues und Pull Requests sind willkommen. Vor dem Einreichen eines PR:

1. Stellen Sie sicher, dass das Frontend fehlerfrei baut (`npm run build`)
2. Halten Sie die Backend-API rückwärtskompatibel
3. Schreiben Sie klare Commit-Nachrichten, die die Änderungen beschreiben

## Lizenz

Dieses Projekt ist unter der [MIT-Lizenz](../LICENSE) als Open Source veröffentlicht.

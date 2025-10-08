# OneDocs Auth Service - Network Topology

> **Amaç:** Auth servisinin network yapısı, port konfigürasyonları ve servisler arası iletişim haritası

## 📋 İçindekiler
- [Genel Bakış](#genel-bakış)
- [Docker Network Yapısı](#docker-network-yapısı)
- [Servis Port Mapping](#servis-port-mapping)
- [Servisler Arası İletişim](#servisler-arası-iletişim)
- [External Access](#external-access)
- [Güvenlik Notları](#güvenlik-notları)

---

## Genel Bakış

### Network Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Host Machine                                │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │           Docker Network: onedocs-network (bridge)          │   │
│  │                                                              │   │
│  │  ┌──────────────────┐    ┌──────────────────┐             │   │
│  │  │   postgres       │    │   auth-api       │             │   │
│  │  │ (onedocs-auth-db)│◄───┤  (auth service)  │             │   │
│  │  │                  │    │                  │             │   │
│  │  │ Port: 5432       │    │ Port: 8000       │             │   │
│  │  └────────┬─────────┘    └────────┬─────────┘             │   │
│  │           │                       │                        │   │
│  │           │ ┌──────────────────┐  │                        │   │
│  │           └►│    pgadmin       │  │                        │   │
│  │             │ (pgadmin4)       │  │                        │   │
│  │             │ Port: 80         │  │                        │   │
│  │             └──────────────────┘  │                        │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                      ▲        ▲           ▲                          │
│                      │        │           │                          │
└──────────────────────┼────────┼───────────┼──────────────────────────┘
                       │        │           │
                    :5441     :5051      :8000
                       │        │           │
                  ┌────┴────────┴───────────┴────┐
                  │   External Access (localhost) │
                  └──────────────────────────────┘
```

---

## Docker Network Yapısı

### Network Tanımı

| Parametre | Değer |
|-----------|-------|
| **Network Name** | `onedocs-network` |
| **Driver** | `bridge` |
| **Subnet** | Auto-assigned (Docker default) |
| **Gateway** | Auto-assigned |
| **Scope** | Local |

### Network Oluşturma Komutu

```bash
# Docker Compose otomatik oluşturur
docker network ls | grep onedocs

# Manuel oluşturma (gerekirse)
docker network create --driver bridge onedocs-network
```

### Network İnceleme

```bash
# Network detayları
docker network inspect onedocs-network

# Bağlı container'ları göster
docker network inspect onedocs-network --format='{{range .Containers}}{{.Name}} {{end}}'
```

---

## Servis Port Mapping

### 1. PostgreSQL Database

| Parametre | Değer |
|-----------|-------|
| **Container Name** | `onedocs-auth-db` |
| **Image** | `postgres:15-alpine` |
| **Internal Port** | `5432` |
| **External Port** | `5441` |
| **Protocol** | TCP |
| **Network** | `onedocs-network` |

**Erişim:**
- **Internal (Docker):** `postgres:5432`
- **External (Host):** `localhost:5441`

**Connection String:**
```bash
# Internal (container'dan)
postgresql://onedocs_user:onedocs_pass_2024@postgres:5432/onedocs_auth

# External (host'tan)
postgresql://onedocs_user:onedocs_pass_2024@localhost:5441/onedocs_auth
```

**Healthcheck:**
```bash
pg_isready -U onedocs_user -d onedocs_auth
```

---

### 2. pgAdmin (Database UI)

| Parametre | Değer |
|-----------|-------|
| **Container Name** | `onedocs-auth-pgadmin` |
| **Image** | `dpage/pgadmin4:latest` |
| **Internal Port** | `80` |
| **External Port** | `5051` |
| **Protocol** | HTTP |
| **Network** | `onedocs-network` |

**Erişim:**
- **External (Browser):** `http://localhost:5051`

**Credentials:**
- Email: `admin@onedocs.com`
- Password: `admin123`

**PostgreSQL Bağlantısı (pgAdmin içinde):**
```
Host: postgres
Port: 5432
Database: onedocs_auth
Username: onedocs_user
Password: onedocs_pass_2024
```

---

### 3. Auth API Service

| Parametre | Değer |
|-----------|-------|
| **Service Name** | `auth-api` (henüz docker-compose'da yok) |
| **Runtime** | Python 3.9 + FastAPI |
| **Internal Port** | `8000` |
| **External Port** | `8000` |
| **Protocol** | HTTP |
| **Network** | `onedocs-network` (production'da) |

**Erişim:**
- **Internal (Docker):** `http://auth-api:8000`
- **External (Development):** `http://localhost:8000`

**Endpoints:**
```bash
# API Docs
http://localhost:8000/docs

# Health Check
http://localhost:8000/health

# API v1
http://localhost:8000/api/v1/...
```

**Environment Variables:**
- `DATABASE_URL`: `postgresql+asyncpg://onedocs_user:onedocs_pass_2024@localhost:5441/onedocs_auth`
- `PORT`: `8000`
- `HOST`: `0.0.0.0`

---

## Servisler Arası İletişim

### Internal Communication (Docker Network)

```
┌─────────────┐
│  auth-api   │
│  :8000      │
└──────┬──────┘
       │ SQL Queries
       ▼
┌─────────────┐
│  postgres   │
│  :5432      │
└─────────────┘
       ▲
       │ SQL Queries (UI)
┌──────┴──────┐
│   pgadmin   │
│   :80       │
└─────────────┘
```

### Communication Table

| Source Service | Target Service | Protocol | Port | Purpose |
|---------------|----------------|----------|------|---------|
| `auth-api` | `postgres` | PostgreSQL | 5432 | Database queries |
| `pgadmin` | `postgres` | PostgreSQL | 5432 | Database management |
| `localhost` | `auth-api` | HTTP | 8000 | API requests |
| `localhost` | `postgres` | PostgreSQL | 5441 | Direct DB access (dev) |
| `localhost` | `pgadmin` | HTTP | 5051 | Web UI access |

### Service Dependencies

```yaml
# docker-compose.yml dependencies
pgadmin:
  depends_on:
    - postgres

auth-api:  # (production)
  depends_on:
    - postgres
```

---

## External Access

### Development Environment

| Service | URL | Credentials |
|---------|-----|-------------|
| **Auth API** | `http://localhost:8000` | JWT Token |
| **API Docs** | `http://localhost:8000/docs` | - |
| **PostgreSQL** | `localhost:5441` | `onedocs_user` / `onedocs_pass_2024` |
| **pgAdmin** | `http://localhost:5051` | `admin@onedocs.com` / `admin123` |

### Production Environment

| Service | URL | Notes |
|---------|-----|-------|
| **Auth API** | `https://auth.onedocs.com` | Behind NGINX/Traefik |
| **PostgreSQL** | Internal only | No external access |
| **pgAdmin** | Disabled | Only in development |

---

## Güvenlik Notları

### ✅ Yapılması Gerekenler

1. **Port Exposure:**
   - Production'da PostgreSQL portunu (`5441`) **kapatın**
   - pgAdmin'i production'da **devre dışı bırakın**
   - Auth API'yi reverse proxy (NGINX) arkasında çalıştırın

2. **Network İzolasyonu:**
   ```bash
   # Production için custom bridge network
   docker network create --driver bridge --subnet 172.18.0.0/16 onedocs-prod-network
   ```

3. **Firewall Rules:**
   ```bash
   # Sadece gerekli portlar açık
   ufw allow 80/tcp    # HTTP (NGINX)
   ufw allow 443/tcp   # HTTPS (NGINX)
   ufw deny 5432/tcp   # PostgreSQL (internal only)
   ufw deny 5441/tcp   # PostgreSQL (external)
   ```

4. **TLS/SSL:**
   ```nginx
   # NGINX SSL Termination
   server {
       listen 443 ssl;
       server_name auth.onedocs.com;

       ssl_certificate /etc/letsencrypt/live/auth.onedocs.com/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/auth.onedocs.com/privkey.pem;

       location / {
           proxy_pass http://auth-api:8000;
       }
   }
   ```

### ❌ Güvenlik Riskleri

| Risk | Açıklama | Çözüm |
|------|----------|-------|
| **Exposed PostgreSQL** | 5441 portu herkese açık | Production'da internal only |
| **Default Passwords** | pgAdmin şifresi basit | Strong password kullanın |
| **No TLS** | HTTP üzerinden trafik | HTTPS/SSL kullanın |
| **pgAdmin in Prod** | Gereksiz UI servisi | Production'da kaldırın |

---

## Docker Compose Referans

### Mevcut Yapı

```yaml
services:
  postgres:
    container_name: onedocs-auth-db
    ports:
      - "5441:5432"
    networks:
      - onedocs-network

  pgadmin:
    container_name: onedocs-auth-pgadmin
    ports:
      - "5051:80"
    networks:
      - onedocs-network
    depends_on:
      - postgres

networks:
  onedocs-network:
    driver: bridge

volumes:
  postgres_data:
  pgadmin_data:
```

### Production Önerisi

```yaml
services:
  postgres:
    container_name: onedocs-auth-db-prod
    # External port kaldırıldı (internal only)
    expose:
      - "5432"
    networks:
      - onedocs-prod-network

  auth-api:
    container_name: onedocs-auth-api-prod
    expose:
      - "8000"
    networks:
      - onedocs-prod-network
    depends_on:
      - postgres

  # pgadmin kaldırıldı (production'da gereksiz)

networks:
  onedocs-prod-network:
    driver: bridge
    internal: false  # NGINX için external gerekli
```

---

## Network Troubleshooting

### Container'lar arası bağlantı testi

```bash
# auth-api container'ından postgres'e bağlan
docker exec -it onedocs-auth-api sh
nc -zv postgres 5432

# PostgreSQL bağlantı testi
docker exec -it onedocs-auth-api python -c "
import asyncpg
import asyncio
async def test():
    conn = await asyncpg.connect('postgresql://onedocs_user:onedocs_pass_2024@postgres:5432/onedocs_auth')
    print('Connection OK')
    await conn.close()
asyncio.run(test())
"
```

### Port dinleme kontrolü

```bash
# Host makineden
netstat -tuln | grep -E '5441|5051|8000'

# Container içinden
docker exec -it onedocs-auth-db netstat -tuln | grep 5432
```

### DNS Resolution

```bash
# Container içinden hostname çözümleme
docker exec -it onedocs-auth-api ping postgres
docker exec -it onedocs-auth-api nslookup postgres
```

---

## Diğer Servislerle Entegrasyon

### OCR Service → Auth Service

```yaml
# OCR Service docker-compose.yml
services:
  ocr-api:
    networks:
      - ocr-network
      - onedocs-network  # Auth network'e de bağlan

networks:
  ocr-network:
    driver: bridge
  onedocs-network:
    external: true  # Mevcut network kullan
```

**İletişim:**
```python
# OCR servisi auth'a istek atar
import httpx

async def verify_token(token: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://auth-api:8000/api/v1/auth/verify",
            headers={"Authorization": f"Bearer {token}"}
        )
        return response.json()
```

### RAG Service → Auth Service

```yaml
services:
  rag-api:
    networks:
      - onedocs-network

networks:
  onedocs-network:
    external: true
```

---

## Monitoring & Logging

### Network Traffic Monitoring

```bash
# tcpdump ile traffic izleme
docker exec -it onedocs-auth-db tcpdump -i eth0 port 5432

# Container logs
docker logs -f onedocs-auth-db
docker logs -f onedocs-auth-api
```

### Metrics

```bash
# Docker stats
docker stats onedocs-auth-db onedocs-auth-api

# Network bandwidth
docker network inspect onedocs-network | jq '.[0].Containers'
```

---

## Changelog

| Tarih | Değişiklik | Sorumlu |
|-------|------------|---------|
| 2025-10-08 | Initial network topology dokümantasyonu | - |
| - | - | - |

---

**Not:** Bu dokümantasyon servis güncellemeleriyle birlikte güncel tutulmalıdır.

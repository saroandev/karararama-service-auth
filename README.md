# OneDocs Auth Service

Merkezi authentication ve authorization servisi. OneDocs ekosistemi için JWT tabanlı kimlik doğrulama, RBAC yetkilendirme ve kullanım takip sistemi.

## İçindekiler

- [Genel Bakış](#genel-bakış)
- [Teknoloji Stack](#teknoloji-stack)
- [Kurulum](#kurulum)
- [Docker Deployment](#docker-deployment)
- [API Endpoints](#api-endpoints)
- [Authentication Flow](#authentication-flow)
- [Authorization & Permissions](#authorization--permissions)
- [Usage Tracking](#usage-tracking)
- [Database Yapısı](#database-yapısı)
- [Proje Yapısı](#proje-yapısı)
- [Testing](#testing)

---

## Genel Bakış

OneDocs mikroservis mimarisinde diğer servislere (OCR, RAG, LLM, Crawler) merkezi kimlik doğrulama ve yetkilendirme hizmeti sağlar.

### Temel İşlevler

- **User Management**: Kayıt, giriş, profil yönetimi
- **JWT Token Management**: Access (30dk) ve refresh token (7 gün)
- **RBAC**: Role-Based Access Control
- **Fine-Grained Permissions**: Resource:Action bazlı izinler
- **Quota Management**: Günlük/aylık kullanım limitleri
- **Usage Tracking**: Servis kullanım takibi
- **Inter-Service Authentication**: Diğer servislerin token doğrulama entegrasyonu

---

## Teknoloji Stack

| Kategori | Teknoloji | Versiyon |
|----------|-----------|----------|
| **Framework** | FastAPI | 0.109.0 |
| **Server** | Uvicorn | 0.27.0 |
| **Database** | PostgreSQL | 15 |
| **ORM** | SQLAlchemy (async) | 2.0.25 |
| **Migration** | Alembic | 1.13.1 |
| **Authentication** | Python-JOSE | 3.3.0 |
| **Password Hashing** | Passlib + Bcrypt | 1.7.4 |
| **Testing** | Pytest | 7.4.4 |
| **Container** | Docker | Latest |

---

## Kurulum

### 1. Gereksinimler

- Python 3.11+
- Docker & Docker Compose
- PostgreSQL 15

### 2. Lokal Development Setup

**Not:** `.env` dosyası git'e commit edilmez. Her developer kendi `.env` dosyasını oluşturmalıdır.

```bash
# Clone repo
git clone <repo-url>
cd onedocs-auth

# Virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Environment variables oluştur
cp .env.example .env
# .env dosyasını düzenle:
# - POSTGRES_HOST=localhost (local Python için)
# - POSTGRES_PASSWORD=güçlü bir şifre
# - JWT_SECRET_KEY=openssl rand -hex 32 ile oluştur

# Start PostgreSQL
docker compose up -d postgres

# Run migrations
alembic upgrade head

# Create default organization (zorunlu)
python create_default_org.py

# Start development server
./start.sh
# veya
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

#### Environment Yapılandırması

| Ortam | POSTGRES_HOST | Açıklama |
|-------|---------------|----------|
| **Local Python** | `localhost` | App local'de, DB Docker'da |
| **Docker Compose** | `postgres` | App ve DB Docker'da |
| **Kubernetes (Cloud)** | `auth.yaml` | ConfigMap + Secret kullanılır |

**Local geliştirme için** `.env` dosyanızda `POSTGRES_HOST=localhost` kullanın.

### 3. Erişim

- API: http://localhost:8001
- API Docs: http://localhost:8001/docs
- pgAdmin: http://localhost:5051

---

## Docker Deployment

### Docker Build

```bash
# Development
docker build --target development -t onedocs-auth:dev .

# Production
docker build --target production -t onedocs-auth:prod .
```

### Docker Compose

Tüm servisleri başlat (postgres, pgadmin, auth-service):

```bash
docker compose up -d
```

Auth servisini yeniden build et:

```bash
docker compose build auth-service
docker compose up -d auth-service
```

Logları izle:

```bash
docker compose logs -f auth-service
```

### Dockerfile Özellikleri

- **Multi-stage build**: base, development, production
- **Python 3.11 slim** image
- **Health check**: `/health` endpoint
- **Production**: Non-root user, 4 workers
- **Development**: Hot-reload

---

## API Endpoints

### Base URL
```
http://localhost:8001/api/v1
```

### Authentication (`/api/v1/auth`)

| Method | Endpoint | Açıklama | Auth |
|--------|----------|----------|------|
| `POST` | `/auth/register` | Yeni kullanıcı kaydı | ❌ |
| `POST` | `/auth/login` | Token al | ❌ |
| `GET` | `/auth/me` | Kullanıcı bilgisi | ✅ |
| `POST` | `/auth/verify` | Token doğrulama (inter-service) | ✅ |

### Users (`/api/v1/users`)

| Method | Endpoint | Açıklama | Auth | Role |
|--------|----------|----------|------|------|
| `GET` | `/users/me` | Profil bilgisi | ✅ | - |
| `PUT` | `/users/me` | Profil güncelle | ✅ | - |
| `GET` | `/users` | Tüm kullanıcılar | ✅ | Admin |
| `GET` | `/users/{user_id}` | Kullanıcı detayı | ✅ | Admin |
| `DELETE` | `/users/{user_id}` | Kullanıcı sil | ✅ | Admin |

### Admin (`/api/v1/admin`)

| Method | Endpoint | Açıklama | Role |
|--------|----------|----------|------|
| `GET` | `/admin/roles` | Rol listesi | Admin |
| `POST` | `/admin/roles` | Rol oluştur | Admin |
| `POST` | `/admin/users/{user_id}/roles/{role_id}` | Rol ata | Admin |
| `DELETE` | `/admin/users/{user_id}/roles/{role_id}` | Rol kaldır | Admin |
| `PUT` | `/admin/users/{user_id}/quotas` | Quota güncelle | Admin |

### Usage (`/api/v1/usage`)

| Method | Endpoint | Açıklama | Auth |
|--------|----------|----------|------|
| `POST` | `/usage/consume` | Kullanım kaydı oluştur | ❌* |
| `GET` | `/usage/stats/{user_id}` | Kullanıcı istatistikleri | ❌* |

*Diğer servisler tarafından kullanılır, user_id ile çalışır.*

### Organizations (`/api/v1/organizations`)

| Method | Endpoint | Açıklama | Auth |
|--------|----------|----------|------|
| `POST` | `/organizations` | Organizasyon oluştur | ✅ Admin |
| `GET` | `/organizations` | Organizasyon listesi | ✅ Admin |
| `GET` | `/organizations/{org_id}` | Organizasyon detayı | ✅ |
| `PUT` | `/organizations/{org_id}` | Organizasyon güncelle | ✅ Admin |

---

## Authentication Flow

### 1. Register

```bash
POST /api/v1/auth/register
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "first_name": "John",
  "last_name": "Doe"
}
```

### 2. Login

```bash
POST /api/v1/auth/login
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}

# Response
{
  "access_token": "eyJhbGci...",
  "refresh_token": "eyJhbGci...",
  "token_type": "bearer"
}
```

### 3. API Request

```bash
GET /api/v1/users/me
Authorization: Bearer eyJhbGci...
```

### 4. Token Verify (Inter-Service)

```bash
POST /api/v1/auth/verify
Authorization: Bearer eyJhbGci...

# Response: user, roles, permissions, quotas, usage
```

---

## Authorization & Permissions

### Varsayılan Roller

| Role | Daily Query | Monthly Query | Daily Docs | Max Doc Size |
|------|-------------|---------------|------------|--------------|
| **admin** | ∞ | ∞ | ∞ | ∞ |
| **user** | 100 | 3000 | 50 | 10 MB |
| **demo** | 10 | 200 | 5 | 5 MB |
| **guest** | 3 | 30 | 0 | 0 MB |

### Permission Formatı

`resource:action` formatında:

```
research:query      → Research servisi sorgu yetkisi
documents:upload    → Dokümman yükleme
documents:delete    → Dokümman silme
*:*                 → Tüm yetkiler (admin)
research:*          → Research için tüm yetkiler
```

### Kod Kullanımı

```python
from app.api.deps import require_role, require_permission

# Rol bazlı
@router.get("/admin/dashboard")
async def dashboard(user: User = Depends(require_role(["admin"]))):
    pass

# İzin bazlı
@router.post("/research/query")
async def query(user: User = Depends(require_permission("research", "query"))):
    pass
```

---

## Usage Tracking

### Kullanım Kaydı

Diğer servisler (OCR, RAG, LLM) bu endpoint'i kullanır:

```bash
POST /api/v1/usage/consume
{
  "user_id": "uuid",
  "service_type": "ocr_text",
  "tokens_used": 1250,
  "processing_time": 2.5,
  "extra_data": {
    "filename": "doc.pdf",
    "pages": 5
  }
}

# Success (200)
{
  "success": true,
  "remaining_credits": 95,
  "credits_consumed": 1
}

# Quota Exceeded (429)
{
  "detail": {
    "error": "Daily query limit exceeded",
    "daily_limit": 100,
    "used_today": 100,
    "reset_time": "2025-10-04T00:00:00Z"
  }
}
```

### Service Types

- `ocr_text` - OCR metin çıkarma
- `ocr_structured` - OCR yapılandırılmış veri
- `rag_query` - RAG sorgu
- `llm_completion` - LLM completion
- `document_process` - Dokümman işleme
- `crawler_job` - Crawler görevi

### İstatistikler

```bash
GET /api/v1/usage/stats/{user_id}

# Response
{
  "daily_usage": { "used": 45, "limit": 100, "remaining": 55 },
  "monthly_usage": { "used": 856, "limit": 3000, "remaining": 2144 },
  "total_stats": {
    "total_queries": 12450,
    "total_documents": 234,
    "total_tokens": 1563200
  }
}
```

---

## Database Yapısı

### ER Diagram

```
┌─────────────────┐       ┌──────────────────┐       ┌─────────────────┐
│     users       │──────<│   user_roles     │>──────│     roles       │
├─────────────────┤       ├──────────────────┤       ├─────────────────┤
│ id (UUID) PK    │       │ user_id (FK)     │       │ id (UUID) PK    │
│ email UNIQUE    │       │ role_id (FK)     │       │ name UNIQUE     │
│ password_hash   │       │ organization_id  │       │ description     │
│ first_name      │       └──────────────────┘       │ default_quotas  │
│ last_name       │                                  └─────────────────┘
│ is_active       │                                          │
│ is_verified     │       ┌──────────────────┐               │
│ quotas          │       │ role_permissions │<──────────────┘
│ usage_stats     │       ├──────────────────┤
└─────────────────┘       │ role_id (FK)     │
        │                 │ permission_id FK │
        │                 └──────────────────┘
        │                          │
        │                          v
        │                 ┌─────────────────┐
        │                 │  permissions    │
        │                 ├─────────────────┤
        │                 │ id (UUID) PK    │
        │                 │ resource        │
        │                 │ action          │
        │                 └─────────────────┘
        │
        v
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│  usage_logs     │       │ refresh_tokens  │       │ organizations   │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id (UUID) PK    │       │ id (UUID) PK    │       │ id (UUID) PK    │
│ user_id (FK)    │       │ user_id (FK)    │       │ name UNIQUE     │
│ service_type    │       │ token_hash      │       │ slug UNIQUE     │
│ tokens_used     │       │ expires_at      │       │ is_active       │
│ processing_time │       │ revoked_at      │       └─────────────────┘
│ extra_data JSONB│       └─────────────────┘
└─────────────────┘
```

### Alembic Migration

```bash
# Yeni migration
alembic revision --autogenerate -m "description"

# Migration uygula
alembic upgrade head

# Geri al
alembic downgrade -1

# Durum
alembic current

# History
alembic history
```

---

## Proje Yapısı

```
onedocs-auth/
├── app/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── auth.py           # Auth endpoints
│   │   │   ├── users.py          # User endpoints
│   │   │   ├── admin.py          # Admin endpoints
│   │   │   ├── usage.py          # Usage endpoints
│   │   │   └── organizations.py  # Organization endpoints
│   │   └── deps.py               # Dependencies
│   ├── core/
│   │   ├── config.py             # Settings
│   │   ├── database.py           # DB connection
│   │   ├── security.py           # JWT, password
│   │   └── permissions.py        # Permission helpers
│   ├── crud/
│   │   ├── user.py
│   │   ├── role.py
│   │   ├── organization.py
│   │   └── usage.py
│   ├── models/
│   │   ├── user.py
│   │   ├── role.py
│   │   ├── permission.py
│   │   ├── organization.py
│   │   ├── usage_log.py
│   │   └── refresh_token.py
│   ├── schemas/
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── role.py
│   │   ├── organization.py
│   │   └── usage.py
│   └── main.py                   # FastAPI app
├── alembic/
│   └── versions/                 # Migrations
├── tests/
│   ├── integration/
│   └── unit/
├── .env                          # Environment variables
├── .env.example
├── Dockerfile                    # Multi-stage build
├── docker-compose.yml            # All services
├── alembic.ini
├── requirements.txt
├── create_default_org.py         # Initial setup script
└── README.md
```

---

## Testing

```bash
# Tüm testler
pytest

# Coverage
pytest --cov=app

# Verbose
pytest -v

# Belirli test
pytest tests/integration/test_auth.py

# Test verification script
./test_verify.sh
```

---

## Utility Scripts

```bash
# Create default organization (ilk kurulumda zorunlu)
python create_default_org.py

# List all users
python list_users.py

# Assign role to user
python assign_role.py

# Reset user password
python reset_password.py

# Sync user roles with organization
python sync_user_roles_org.py
```

---

## Environment Variables

```env
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5441
POSTGRES_USER=onedocs_user
POSTGRES_PASSWORD=onedocs_pass_2024
POSTGRES_DB=onedocs_auth
DATABASE_URL=postgresql+asyncpg://user:pass@host:port/db

# JWT
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Server
HOST=0.0.0.0
PORT=8001
DEBUG=True

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:8000

# pgAdmin
PGADMIN_DEFAULT_EMAIL=admin@onedocs.com
PGADMIN_DEFAULT_PASSWORD=admin123
PGADMIN_PORT=5051
```

---

## pgAdmin Kullanımı

1. http://localhost:5051
2. Login: `admin@onedocs.com` / `admin123`
3. Add Server:
   - Host: `postgres` (Docker network)
   - Port: `5432`
   - Database: `onedocs_auth`
   - Username: `onedocs_user`
   - Password: `onedocs_pass_2024`

---

## Security Best Practices

- JWT_SECRET_KEY güçlü ve gizli olmalı
- Production'da HTTPS kullan
- CORS doğru yapılandır
- Password policy uygula (min 8 karakter)
- Access token kısa ömürlü (max 60dk)
- Database credentials güvenli

---

## Health Check

```bash
curl http://localhost:8001/health

# Response
{
  "status": "healthy",
  "app": "OneDocs Auth Service",
  "version": "1.0.0"
}
```

---

**OneDocs Auth Service** - JWT tabanlı mikroservis auth sistemi

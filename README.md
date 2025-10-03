# OneDocs Auth Service

🔐 **Merkezi Authentication ve Authorization Servisi** - OneDocs ekosistemi için JWT tabanlı kimlik doğrulama, RBAC (Role-Based Access Control) yetkilendirme ve kullanım takip sistemi.

## 📋 İçindekiler

- [Genel Bakış](#genel-bakış)
- [Özellikler](#özellikler)
- [Teknoloji Stack](#teknoloji-stack)
- [Kurulum](#kurulum)
- [API Dokümantasyonu](#api-dokümantasyonu)
- [Authentication Flow](#authentication-flow)
- [Authorization & Permissions](#authorization--permissions)
- [Usage Tracking](#usage-tracking)
- [Database Yapısı](#database-yapısı)
- [Güvenlik](#güvenlik)
- [Deployment](#deployment)
- [Örnek Kullanım Senaryoları](#örnek-kullanım-senaryoları)

---

## 🎯 Genel Bakış

OneDocs Auth Service, mikroservis mimarisinde çalışan diğer servislere (OCR, RAG, LLM, Crawler) merkezi kimlik doğrulama ve yetkilendirme hizmeti sağlar. JWT token tabanlı stateless authentication ile yüksek performanslı ve ölçeklenebilir bir yapı sunar.

### Temel İşlevler

- **Kullanıcı Yönetimi**: Kayıt, giriş, profil güncelleme
- **JWT Token Management**: Access ve refresh token oluşturma/doğrulama
- **RBAC (Role-Based Access Control)**: Rol tabanlı yetkilendirme
- **Fine-Grained Permissions**: Resource:Action bazlı izin sistemi
- **Quota Management**: Günlük/aylık kullanım limitleri
- **Usage Tracking**: Servis kullanım takibi ve istatistikler
- **Inter-Service Authentication**: Diğer servislerin token doğrulama entegrasyonu

---

## 🚀 Özellikler

### Authentication & Authorization
- ✅ JWT (JSON Web Tokens) tabanlı stateless authentication
- ✅ Access Token (30 dakika) + Refresh Token (7 gün) mekanizması
- ✅ Bcrypt ile şifreli password hashing
- ✅ RBAC (Role-Based Access Control) sistemi
- ✅ Fine-grained permission kontrolü (resource:action)
- ✅ Token doğrulama endpoint'i (diğer servisler için)

### User Management
- ✅ Kullanıcı kaydı ve profil yönetimi
- ✅ Email uniqueness kontrolü
- ✅ Aktif/pasif kullanıcı durumu
- ✅ Son giriş zamanı takibi
- ✅ Rol atama/çıkarma (admin)

### Quota & Usage Management
- ✅ Kullanıcı bazlı günlük/aylık sorgu limitleri
- ✅ Dokümman yükleme limitleri
- ✅ Maksimum dosya boyutu kontrolü
- ✅ Otomatik kullanım takibi
- ✅ Rate limiting (429 Too Many Requests)
- ✅ Kalan kredi/quota bilgisi

### Database & Performance
- ✅ PostgreSQL 15 ile async database işlemleri
- ✅ SQLAlchemy ORM (async support)
- ✅ Alembic migration yönetimi
- ✅ Connection pooling
- ✅ Indexing stratejileri

### Developer Experience
- ✅ FastAPI otomatik OpenAPI dokümantasyonu
- ✅ pgAdmin database yönetim arayüzü
- ✅ Docker & Docker Compose desteği
- ✅ Pytest ile test altyapısı
- ✅ CORS middleware

---

## 🛠 Teknoloji Stack

| Kategori | Teknoloji | Versiyon |
|----------|-----------|----------|
| **Framework** | FastAPI | 0.109.0 |
| **Server** | Uvicorn | 0.27.0 |
| **Database** | PostgreSQL | 15 |
| **ORM** | SQLAlchemy (async) | 2.0.25 |
| **Migration** | Alembic | 1.13.1 |
| **Authentication** | Python-JOSE | 3.3.0 |
| **Password Hashing** | Passlib + Bcrypt | 1.7.4 |
| **Validation** | Pydantic | 2.5.0 |
| **Testing** | Pytest | 7.4.4 |
| **Container** | Docker | Latest |

---

## 📦 Kurulum

### 1. Gereksinimler

```bash
- Python 3.9+
- Docker & Docker Compose
- PostgreSQL 15 (Docker ile sağlanır)
```

### 2. Repository'yi Klonlayın

```bash
git clone <repo-url>
cd onedocs-auth
```

### 3. Virtual Environment Oluşturun

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# veya
venv\Scripts\activate  # Windows
```

### 4. Bağımlılıkları Yükleyin

```bash
pip install -r requirements.txt
```

### 5. Environment Variables Ayarlayın

`.env.example` dosyasını `.env` olarak kopyalayın ve düzenleyin:

```bash
cp .env.example .env
```

**.env Örnek İçerik:**

```env
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5441
POSTGRES_USER=onedocs_user
POSTGRES_PASSWORD=onedocs_pass_2024
POSTGRES_DB=onedocs_auth
DATABASE_URL=postgresql+asyncpg://onedocs_user:onedocs_pass_2024@localhost:5441/onedocs_auth

# JWT Security
JWT_SECRET_KEY=your-super-secret-key-change-this-in-production
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

### 6. PostgreSQL ve pgAdmin'i Başlatın

```bash
docker compose up -d
```

### 7. Database Migration'larını Çalıştırın

```bash
# Tüm migration'ları uygula
alembic upgrade head

# Başlangıç verilerini yükle (roles, permissions)
# Bu adım için manuel SQL script veya seed script çalıştırılmalı
```

### 8. Uygulamayı Başlatın

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

**Servis Erişim:**
- API: http://localhost:8001
- API Docs (Swagger): http://localhost:8001/docs
- ReDoc: http://localhost:8001/redoc
- pgAdmin: http://localhost:5051

---

## 📚 API Dokümantasyonu

### Base URL

```
http://localhost:8001/api/v1
```

### Endpoint Grupları

#### 🔑 Authentication Endpoints (`/api/v1/auth`)

| Method | Endpoint | Açıklama | Auth |
|--------|----------|----------|------|
| `POST` | `/auth/register` | Yeni kullanıcı kaydı | ❌ |
| `POST` | `/auth/login` | Kullanıcı girişi (token al) | ❌ |
| `GET` | `/auth/me` | Giriş yapan kullanıcı bilgisi | ✅ |
| `POST` | `/auth/verify` | Token doğrulama (diğer servisler için) | ✅ |

#### 👤 User Management Endpoints (`/api/v1/users`)

| Method | Endpoint | Açıklama | Auth | Role |
|--------|----------|----------|------|------|
| `GET` | `/users/me` | Kullanıcı bilgisi (roles ile) | ✅ | - |
| `PUT` | `/users/me` | Profil güncelleme | ✅ | - |
| `GET` | `/users` | Tüm kullanıcıları listele | ✅ | Admin |
| `GET` | `/users/{user_id}` | Kullanıcı detayı | ✅ | Admin |
| `DELETE` | `/users/{user_id}` | Kullanıcı silme | ✅ | Admin |

#### 🔐 Admin Endpoints (`/api/v1/admin`)

| Method | Endpoint | Açıklama | Auth | Role |
|--------|----------|----------|------|------|
| `GET` | `/admin/roles` | Tüm rolleri listele | ✅ | Admin |
| `POST` | `/admin/roles` | Yeni rol oluştur | ✅ | Admin |
| `POST` | `/admin/users/{user_id}/roles/{role_id}` | Kullanıcıya rol ata | ✅ | Admin |
| `DELETE` | `/admin/users/{user_id}/roles/{role_id}` | Rolü kaldır | ✅ | Admin |
| `PUT` | `/admin/users/{user_id}/quotas` | Kullanıcı quota güncelle | ✅ | Admin |

#### 📊 Usage Tracking Endpoints (`/api/v1/usage`)

| Method | Endpoint | Açıklama | Auth |
|--------|----------|----------|------|
| `POST` | `/usage/consume` | Kullanım kaydı oluştur | ❌* |
| `GET` | `/usage/stats/{user_id}` | Kullanıcı istatistikleri | ❌* |

*\*Not: Bu endpoint'ler diğer servisler tarafından kullanılır, JWT yerine user_id ile çalışır.*

---

## 🔐 Authentication Flow

### 1. Kullanıcı Kaydı (Register)

```bash
POST /api/v1/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "first_name": "John",
  "last_name": "Doe"
}
```

**Response:**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "is_active": true,
  "is_verified": false,
  "created_at": "2025-10-03T10:30:00Z"
}
```

### 2. Kullanıcı Girişi (Login)

```bash
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Access Token Payload:**
```json
{
  "sub": "123e4567-e89b-12d3-a456-426614174000",
  "email": "user@example.com",
  "roles": ["user"],
  "permissions": [
    {"resource": "research", "action": "query"},
    {"resource": "documents", "action": "upload"}
  ],
  "quotas": {
    "daily_query_limit": 100,
    "monthly_query_limit": 3000,
    "daily_document_limit": 50
  },
  "exp": 1696333800,
  "iat": 1696332000,
  "type": "access"
}
```

### 3. API İsteklerinde Token Kullanımı

```bash
GET /api/v1/users/me
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 4. Token Doğrulama (Diğer Servisler İçin)

```bash
POST /api/v1/auth/verify
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Response:**
```json
{
  "valid": true,
  "user": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "is_active": true
  },
  "roles": ["user"],
  "permissions": [
    {"resource": "research", "action": "query"},
    {"resource": "documents", "action": "upload"}
  ],
  "quotas": {
    "daily_query_limit": 100,
    "monthly_query_limit": 3000,
    "daily_document_limit": 50,
    "max_document_size_mb": 10
  },
  "usage": {
    "total_queries_used": 45,
    "total_documents_uploaded": 12
  }
}
```

---

## 🛡️ Authorization & Permissions

### RBAC (Role-Based Access Control) Sistemi

Sistem, **rol tabanlı** ve **izin bazlı** iki katmanlı yetkilendirme kullanır:

1. **Roles (Roller)**: Kullanıcı gruplarını temsil eder
2. **Permissions (İzinler)**: Resource:Action formatında granüler izinler

### Varsayılan Roller ve Quota'lar

| Role | Daily Query | Monthly Query | Daily Docs | Max Doc Size | Açıklama |
|------|-------------|---------------|------------|--------------|----------|
| **admin** | ∞ (NULL) | ∞ (NULL) | ∞ (NULL) | ∞ (NULL) | Tam yetkili yönetici |
| **user** | 100 | 3000 | 50 | 10 MB | Normal kullanıcı |
| **demo** | 10 | 200 | 5 | 5 MB | Demo/deneme kullanıcı |
| **guest** | 3 | 30 | 0 | 0 MB | Misafir kullanıcı |

### Permission Formatı

Permissions `resource:action` formatında tanımlanır:

```
research:query      → Research servisi sorgu yetkisi
documents:upload    → Dokümman yükleme yetkisi
documents:delete    → Dokümman silme yetkisi
users:read          → Kullanıcı okuma yetkisi
users:update        → Kullanıcı güncelleme yetkisi
*:*                 → Tüm kaynaklar için tam yetki (admin)
research:*          → Research için tüm yetkiler
```

### Wildcard Permissions

- `*:*` → Tüm kaynaklara tüm aksiyonlar için tam yetki
- `research:*` → Research kaynağı için tüm aksiyonlar
- `*:read` → Tüm kaynaklar için read aksiyonu

### Kod Örnekleri

#### 1. Rol Bazlı Yetkilendirme

```python
from app.api.deps import require_role

@router.get("/admin/dashboard")
async def admin_dashboard(
    user: User = Depends(require_role(["admin"]))
):
    # Sadece admin rolüne sahip kullanıcılar erişebilir
    return {"message": "Welcome to admin dashboard"}
```

#### 2. İzin Bazlı Yetkilendirme

```python
from app.api.deps import require_permission

@router.post("/research/query")
async def create_query(
    user: User = Depends(require_permission("research", "query"))
):
    # research:query iznine sahip kullanıcılar erişebilir
    return {"message": "Query created"}
```

#### 3. Admin Bypass

```python
# Admin kullanıcılar TÜM role ve permission kontrollerini otomatik geçer
# Kod içinde "admin" in user_roles kontrolü yapılır
```

---

## 📊 Usage Tracking

### Kullanım Kaydı Oluşturma

Diğer servisler (OCR, RAG, LLM) kullanım kaydı oluşturmak için bu endpoint'i kullanır:

```bash
POST /api/v1/usage/consume
Content-Type: application/json

{
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "service_type": "ocr_text",
  "tokens_used": 1250,
  "processing_time": 2.5,
  "extra_data": {
    "filename": "document.pdf",
    "file_size": 2048576,
    "pages": 5,
    "model": "gpt-4"
  }
}
```

**Success Response (200):**
```json
{
  "success": true,
  "remaining_credits": 95,
  "credits_consumed": 1,
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "message": "Usage recorded successfully"
}
```

**Error Response - Daily Limit Exceeded (429):**
```json
{
  "detail": {
    "success": false,
    "error": "Daily query limit exceeded",
    "daily_limit": 100,
    "used_today": 100,
    "reset_time": "2025-10-04T00:00:00Z"
  }
}
```

**Error Response - Monthly Limit Exceeded (429):**
```json
{
  "detail": {
    "success": false,
    "error": "Monthly query limit exceeded",
    "monthly_limit": 3000,
    "used_this_month": 3000,
    "reset_time": "2025-11-01T00:00:00Z"
  }
}
```

### Kullanım İstatistikleri

```bash
GET /api/v1/usage/stats/{user_id}
```

**Response:**
```json
{
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "daily_usage": {
    "used": 45,
    "limit": 100,
    "remaining": 55
  },
  "monthly_usage": {
    "used": 856,
    "limit": 3000,
    "remaining": 2144
  },
  "total_stats": {
    "total_queries": 12450,
    "total_documents": 234,
    "total_tokens": 1563200
  }
}
```

### Quota Kontrolü Akışı

```
┌───────────────────┐
│ OCR Service       │
│ Request           │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ POST /usage/      │
│ consume           │
└─────────┬─────────┘
          │
          ▼
    ┌─────────┐
    │ User    │  No    ┌───────────┐
    │ Active? ├───────►│ 403       │
    └────┬────┘        │ Forbidden │
         │ Yes         └───────────┘
         ▼
    ┌─────────┐
    │ Daily   │  Exceeded  ┌───────────┐
    │ Limit?  ├───────────►│ 429 Too   │
    └────┬────┘            │ Many      │
         │ OK              │ Requests  │
         ▼                 └───────────┘
    ┌─────────┐
    │ Monthly │  Exceeded
    │ Limit?  ├───────────►
    └────┬────┘
         │ OK
         ▼
┌───────────────────┐
│ Create Usage Log  │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Update User Stats │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Return Success +  │
│ Remaining Credits │
└───────────────────┘
```

### Service Type'lar

- `ocr_text` - OCR metin çıkarma
- `ocr_structured` - OCR yapılandırılmış veri
- `ocr_text_file` - OCR dosya işleme
- `rag_query` - RAG sorgu
- `llm_completion` - LLM completion
- `document_process` - Dokümman işleme
- `crawler_job` - Crawler görevi

---

## 🗄️ Database Yapısı

### ER Diagram

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│     users       │────────<│   user_roles     │>────────│     roles       │
├─────────────────┤         ├──────────────────┤         ├─────────────────┤
│ id (UUID) PK    │         │ user_id (FK)     │         │ id (UUID) PK    │
│ email UNIQUE    │         │ role_id (FK)     │         │ name UNIQUE     │
│ password_hash   │         └──────────────────┘         │ description     │
│ first_name      │                                      │ default_quotas  │
│ last_name       │                                      └─────────────────┘
│ is_active       │                                              │
│ is_verified     │                                              │
│ quotas          │         ┌──────────────────┐                 │
│ usage_stats     │         │ role_permissions │<────────────────┘
└─────────────────┘         ├──────────────────┤
        │                   │ role_id (FK)     │
        │                   │ permission_id FK │
        │                   └──────────────────┘
        │                            │
        │                            v
        │                   ┌─────────────────┐
        │                   │  permissions    │
        │                   ├─────────────────┤
        │                   │ id (UUID) PK    │
        │                   │ resource        │
        │                   │ action          │
        │                   │ description     │
        │                   └─────────────────┘
        │
        v
┌─────────────────┐         ┌─────────────────┐
│  usage_logs     │         │ refresh_tokens  │
├─────────────────┤         ├─────────────────┤
│ id (UUID) PK    │         │ id (UUID) PK    │
│ user_id (FK)    │         │ user_id (FK)    │
│ service_type    │         │ token_hash      │
│ tokens_used     │         │ expires_at      │
│ processing_time │         │ revoked_at      │
│ created_at      │         │ device_info     │
│ extra_data JSONB│         └─────────────────┘
└─────────────────┘
```

### Tablo Detayları

#### 📌 users

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    last_login_at TIMESTAMP,

    -- Quota Limitleri (NULL = sınırsız)
    daily_query_limit INTEGER,
    monthly_query_limit INTEGER,
    daily_document_upload_limit INTEGER,
    max_document_size_mb INTEGER DEFAULT 10,

    -- Kullanım İstatistikleri
    total_queries_used INTEGER DEFAULT 0,
    total_documents_uploaded INTEGER DEFAULT 0,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### 📌 roles

```sql
CREATE TABLE roles (
    id UUID PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,

    -- Varsayılan Quota'lar (role atandığında kullanıcıya kopyalanır)
    default_daily_query_limit INTEGER,
    default_monthly_query_limit INTEGER,
    default_daily_document_limit INTEGER,
    default_max_document_size_mb INTEGER DEFAULT 10,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### 📌 permissions

```sql
CREATE TABLE permissions (
    id UUID PRIMARY KEY,
    resource VARCHAR(100) NOT NULL,  -- research, documents, users, etc.
    action VARCHAR(50) NOT NULL,     -- query, upload, read, update, delete, *
    description TEXT,

    UNIQUE(resource, action)
);
```

#### 📌 usage_logs

```sql
CREATE TABLE usage_logs (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    service_type VARCHAR(50) NOT NULL,
    tokens_used INTEGER DEFAULT 0,
    processing_time FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    extra_data JSONB,  -- {filename, file_size, model, etc.}

    UNIQUE(user_id, created_at, service_type)  -- İdempotency
);
```

### Alembic Migration Komutları

```bash
# Yeni migration oluştur
alembic revision --autogenerate -m "add new column"

# Migration'ları uygula
alembic upgrade head

# Son migration'ı geri al
alembic downgrade -1

# Migration history
alembic history

# Mevcut migration durumu
alembic current
```

---

## 🔒 Güvenlik

### Best Practices

#### 1. JWT Secret Key

```bash
# Güçlü bir secret key üretin
python -c "import secrets; print(secrets.token_urlsafe(64))"

# .env dosyasına ekleyin
JWT_SECRET_KEY=your-generated-secret-key-here
```

**⚠️ Önemli:** Production'da bu anahtarı **asla** git'e commit etmeyin!

#### 2. Password Hashing

```python
# Bcrypt ile hash (otomatik salt eklenir)
password_hash = password_handler.hash_password("user_password")

# Doğrulama
is_valid = password_handler.verify_password("user_password", password_hash)
```

**Özellikler:**
- Bcrypt algoritması (cost factor: 12)
- Otomatik salt generation
- Brute-force saldırılara karşı yavaş hashing

#### 3. Token Expiration

```python
# Access Token: 30 dakika (kısa ömürlü)
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Refresh Token: 7 gün (uzun ömürlü)
REFRESH_TOKEN_EXPIRE_DAYS=7
```

#### 4. CORS Configuration

```python
# Sadece güvenilir origin'lere izin verin
CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com

# Tüm origin'lere izin vermeyin (güvensiz!)
# CORS_ORIGINS=* ← YAPMAYIN!
```

#### 5. HTTPS Kullanımı

```bash
# Production'da HTTPS zorunlu
# Nginx/Cloudflare ile SSL termination yapın
```

#### 6. Rate Limiting

```python
# Quota sistemi otomatik rate limiting sağlar
# 429 Too Many Requests döner
```

### Güvenlik Kontrol Listesi

- [ ] JWT_SECRET_KEY güçlü ve gizli
- [ ] HTTPS kullanılıyor
- [ ] CORS doğru yapılandırılmış
- [ ] Password policy uygulanmış (min 8 karakter, büyük/küçük harf, rakam)
- [ ] Database credentials güvenli
- [ ] Access token'lar kısa ömürlü (max 60 dakika)
- [ ] SQL injection koruması (SQLAlchemy ORM kullanımı)
- [ ] XSS koruması (FastAPI otomatik)
- [ ] CSRF koruması (stateless JWT kullanımı)

---

## 🐳 Deployment

### Docker ile Production Deployment

#### 1. Dockerfile (Örnek)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Bağımlılıkları yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama dosyalarını kopyala
COPY ./app ./app
COPY ./alembic ./alembic
COPY alembic.ini .

# Migration'ları çalıştır
CMD alembic upgrade head && \
    uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 4
```

#### 2. Docker Compose (Production)

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  auth-service:
    build: .
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - ACCESS_TOKEN_EXPIRE_MINUTES=30
      - REFRESH_TOKEN_EXPIRE_DAYS=7
    ports:
      - "8001:8001"
    depends_on:
      - postgres

volumes:
  postgres_data:
```

### Environment Variables (Production)

```bash
# Database (Production)
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_USER=onedocs_prod_user
POSTGRES_PASSWORD=<strong-password>
POSTGRES_DB=onedocs_auth_prod
DATABASE_URL=postgresql+asyncpg://onedocs_prod_user:<password>@postgres:5432/onedocs_auth_prod

# JWT (Production)
JWT_SECRET_KEY=<generate-with-secrets.token_urlsafe(64)>
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Server
HOST=0.0.0.0
PORT=8001
DEBUG=False

# CORS
CORS_ORIGINS=https://yourdomain.com
```

### Health Check Endpoint

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

## 💡 Örnek Kullanım Senaryoları

### Senaryo 1: Yeni Kullanıcı Kaydı ve İlk Query

```python
import requests

BASE_URL = "http://localhost:8001/api/v1"

# 1. Kullanıcı kaydı
register_response = requests.post(
    f"{BASE_URL}/auth/register",
    json={
        "email": "john@example.com",
        "password": "SecurePass123!",
        "first_name": "John",
        "last_name": "Doe"
    }
)
user = register_response.json()
print(f"User created: {user['id']}")

# 2. Login (token al)
login_response = requests.post(
    f"{BASE_URL}/auth/login",
    json={
        "email": "john@example.com",
        "password": "SecurePass123!"
    }
)
tokens = login_response.json()
access_token = tokens["access_token"]

# 3. Profil bilgilerini al
headers = {"Authorization": f"Bearer {access_token}"}
me_response = requests.get(f"{BASE_URL}/users/me", headers=headers)
user_profile = me_response.json()
print(f"User: {user_profile['email']}, Roles: {user_profile['roles']}")
```

### Senaryo 2: Admin Kullanıcı Oluşturma ve Rol Atama

```python
# 1. Normal kullanıcı oluştur
user_response = requests.post(
    f"{BASE_URL}/auth/register",
    json={
        "email": "alice@example.com",
        "password": "AdminPass123!"
    }
)
user_id = user_response.json()["id"]

# 2. Admin token ile rol ata
admin_headers = {"Authorization": f"Bearer {admin_access_token}"}

# Rol listesini al
roles_response = requests.get(f"{BASE_URL}/admin/roles", headers=admin_headers)
admin_role = next(r for r in roles_response.json() if r["name"] == "admin")

# Admin rolünü ata
assign_response = requests.post(
    f"{BASE_URL}/admin/users/{user_id}/roles/{admin_role['id']}",
    headers=admin_headers
)
print(f"Admin role assigned: {assign_response.json()}")
```

### Senaryo 3: OCR Servisi Entegrasyonu

```python
# OCR servisi tarafından kullanım kaydı oluşturma

def record_ocr_usage(user_id: str, filename: str, tokens: int):
    """OCR kullanımını kaydet"""
    response = requests.post(
        f"{BASE_URL}/usage/consume",
        json={
            "user_id": user_id,
            "service_type": "ocr_text_file",
            "tokens_used": tokens,
            "processing_time": 2.5,
            "extra_data": {
                "filename": filename,
                "file_size": 2048576,
                "pages": 5
            }
        }
    )

    if response.status_code == 200:
        result = response.json()
        print(f"Usage recorded. Remaining credits: {result['remaining_credits']}")
        return True
    elif response.status_code == 429:
        # Quota aşıldı
        error = response.json()["detail"]
        print(f"Quota exceeded: {error['error']}")
        print(f"Reset time: {error['reset_time']}")
        return False
    else:
        print(f"Error: {response.json()}")
        return False

# Kullanım
record_ocr_usage(
    user_id="123e4567-e89b-12d3-a456-426614174000",
    filename="document.pdf",
    tokens=1250
)
```

### Senaryo 4: Token Doğrulama (Mikroservis Arası)

```python
# RAG servisi auth token'ı doğrular

def verify_user_token(access_token: str):
    """Diğer servisler için token doğrulama"""
    response = requests.post(
        f"{BASE_URL}/auth/verify",
        headers={"Authorization": f"Bearer {access_token}"}
    )

    if response.status_code == 200:
        data = response.json()
        return {
            "user_id": data["user"]["id"],
            "email": data["user"]["email"],
            "roles": data["roles"],
            "permissions": data["permissions"],
            "quotas": data["quotas"]
        }
    else:
        return None

# RAG endpoint örneği
@app.post("/api/v1/rag/query")
async def rag_query(query: str, authorization: str = Header(None)):
    token = authorization.replace("Bearer ", "")
    user_info = verify_user_token(token)

    if not user_info:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Permission kontrolü
    has_permission = any(
        p["resource"] == "research" and p["action"] in ["query", "*"]
        for p in user_info["permissions"]
    )

    if not has_permission:
        raise HTTPException(status_code=403, detail="Permission denied")

    # Query işle...
    return {"result": "RAG response"}
```

### Senaryo 5: Kullanım İstatistikleri Dashboard

```python
def get_user_dashboard(user_id: str):
    """Kullanıcı dashboard bilgileri"""
    response = requests.get(f"{BASE_URL}/usage/stats/{user_id}")
    stats = response.json()

    print(f"=== User Dashboard ===")
    print(f"Daily: {stats['daily_usage']['used']}/{stats['daily_usage']['limit']} "
          f"(Remaining: {stats['daily_usage']['remaining']})")
    print(f"Monthly: {stats['monthly_usage']['used']}/{stats['monthly_usage']['limit']} "
          f"(Remaining: {stats['monthly_usage']['remaining']})")
    print(f"Total Queries: {stats['total_stats']['total_queries']}")
    print(f"Total Documents: {stats['total_stats']['total_documents']}")
    print(f"Total Tokens: {stats['total_stats']['total_tokens']}")

    return stats
```

---

## 🔧 Geliştirme

### Proje Yapısı

```
onedocs-auth/
├── app/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── __init__.py       # API router
│   │   │   ├── auth.py           # Auth endpoints
│   │   │   ├── users.py          # User endpoints
│   │   │   ├── admin.py          # Admin endpoints
│   │   │   └── usage.py          # Usage endpoints
│   │   └── deps.py               # Dependencies (auth, permissions)
│   ├── core/
│   │   ├── config.py             # Settings (Pydantic)
│   │   ├── database.py           # DB connection
│   │   └── security.py           # JWT, password hashing
│   ├── crud/
│   │   ├── user.py               # User CRUD
│   │   ├── role.py               # Role CRUD
│   │   └── usage.py              # Usage CRUD
│   ├── models/
│   │   ├── user.py               # User model
│   │   ├── role.py               # Role model
│   │   ├── permission.py         # Permission model
│   │   ├── usage_log.py          # UsageLog model
│   │   └── refresh_token.py      # RefreshToken model
│   ├── schemas/
│   │   ├── auth.py               # Auth schemas
│   │   ├── user.py               # User schemas
│   │   ├── role.py               # Role schemas
│   │   └── usage.py              # Usage schemas
│   ├── middleware/
│   │   └── __init__.py
│   └── main.py                   # FastAPI app
├── alembic/
│   ├── versions/                 # Migration files
│   └── env.py
├── tests/
│   ├── integration/
│   └── unit/
├── .env                          # Environment variables
├── .env.example                  # Example env file
├── alembic.ini                   # Alembic config
├── docker-compose.yml            # Docker services
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

### Testing

```bash
# Tüm testleri çalıştır
pytest

# Coverage ile
pytest --cov=app

# Belirli bir test dosyası
pytest tests/integration/test_auth.py

# Verbose mode
pytest -v
```

### Code Quality

```bash
# Linting
flake8 app/

# Type checking
mypy app/

# Format checking
black --check app/
```

---

## 🗄️ pgAdmin Kullanımı

pgAdmin'e erişmek için:

1. **Tarayıcıda açın:** http://localhost:5051
2. **Login:**
   - Email: `admin@onedocs.com`
   - Password: `admin123`

3. **PostgreSQL Server Ekleyin:**
   - **General Tab:**
     - Name: `OneDocs Auth`
   - **Connection Tab:**
     - Host: `postgres` (Docker network içinde)
     - Port: `5432`
     - Database: `onedocs_auth`
     - Username: `onedocs_user`
     - Password: `onedocs_pass_2024`
   - **Save**

---

## ❓ Sık Sorulan Sorular (FAQ)

### Q: Token expire olduğunda ne yapmalıyım?
A: Refresh token kullanarak yeni bir access token alabilirsiniz (henüz endpoint eklenmemiş).

### Q: Kullanıcı quota'sını nasıl güncellerim?
A: Admin kullanıcı `/api/v1/admin/users/{user_id}/quotas` endpoint'ini kullanarak güncelleyebilir.

### Q: Permission sistemi nasıl çalışır?
A: `resource:action` formatında izinler tanımlanır. Admin kullanıcılar tüm izinlere sahiptir. Wildcard (`*`) desteklenir.

### Q: Usage tracking idempotent mi?
A: Evet, `(user_id, created_at, service_type)` unique constraint ile aynı kaydın tekrar oluşturulması engellenir.

### Q: Rate limiting nasıl çalışır?
A: Günlük/aylık quota kontrolleri `/usage/consume` endpoint'inde yapılır. Limit aşımında 429 döner.

---

## 📄 Hata Kodları

| HTTP Code | Açıklama | Örnek |
|-----------|----------|-------|
| `200` | Success | İşlem başarılı |
| `201` | Created | Yeni kaynak oluşturuldu |
| `400` | Bad Request | Geçersiz input verisi |
| `401` | Unauthorized | Token geçersiz/eksik |
| `403` | Forbidden | Yetki yetersiz |
| `404` | Not Found | Kaynak bulunamadı |
| `429` | Too Many Requests | Quota/rate limit aşıldı |
| `500` | Internal Server Error | Sunucu hatası |

---

## 📞 Destek & Katkı

- **Issues:** GitHub Issues
- **Pull Requests:** Contributions welcome!
- **Documentation:** `/docs` endpoint

---

## 📄 Lisans

MIT License

---

**🤖 OneDocs Auth Service** - Built with FastAPI, PostgreSQL, and JWT

*Generated with [Claude Code](https://claude.com/claude-code)*

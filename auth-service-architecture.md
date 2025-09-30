# Authentication Service Architecture

## Proje Genel Bakış

LLM tabanlı Research servisi için merkezi authentication ve authorization sistemi. Kullanıcı kimlik doğrulama, yetkilendirme ve **quota/rate limiting** yönetimini tek noktadan kontrol eder.

### Servis Yapısı
- **Auth Service**: Kullanıcı, rol, yetki ve quota yönetimi
- **Research Service**: LLM sorgu işleme, belge yükleme
- **Diğer LLM Servisleri**: Farklı AI özellikleri

### Temel Özellikler
- Kullanıcı bazlı query limitleri (günlük/aylık)
- Rol bazlı yetkilendirme (Admin, User, Demo, Guest)
- Belge yükleme limitleri
- Real-time quota tracking (Redis)

## Teknoloji Stack Önerileri

### Backend Framework
- **FastAPI (Python)**: Modern, hızlı, async/await desteği, otomatik API dokümantasyonu, type hints
  - Diğer Python servislerinizle uyumlu
  - Pydantic ile güçlü validation
  - SQLAlchemy ORM desteği
  - JWT libraries: python-jose, PyJWT

**Seçilen Stack**: FastAPI + Python 3.11+

### Veritabanı
- **PostgreSQL**: İlişkisel veri, ACID uyumlu, kullanıcı/rol yönetimi için ideal
  - SQLAlchemy ORM kullanılacak
  - Alembic ile migration
  - Quota limitleri ve kullanım kayıtları
- **Redis**: Critical - Real-time quota tracking için
  - Query counter (günlük/aylık)
  - Token cache ve blacklist
  - Rate limiting
  - redis-py veya aioredis
- **MongoDB**: Opsiyonel - Query history ve audit trail için

### Authentication Stratejisi
- **JWT (JSON Web Tokens)**: Stateless, ölçeklenebilir
  - Access Token (kısa ömürlü: 15-30 dakika)
  - Refresh Token (uzun ömürlü: 7-30 gün)
  - Library: python-jose[cryptography] veya PyJWT
- **Password Hashing**: bcrypt veya passlib
- **OAuth 2.0**: Üçüncü parti entegrasyonlar için (Google, GitHub, vb.)
- **2FA**: TOTP tabanlı (pyotp library)

### API Gateway Pattern
- **Kong**, **Traefik**, veya **NGINX**: API Gateway olarak
- Auth servisini gateway arkasına koy
- Gateway'de JWT validation middleware

## Mimari Tasarım

### 1. Servis Yapısı

```
┌─────────────────────────────────────────────────────────┐
│                     API Gateway                          │
│              (JWT Validation Middleware)                 │
└────────────┬─────────────────────────────┬──────────────┘
             │                             │
    ┌────────▼────────┐         ┌─────────▼──────────┐
    │  Auth Service   │         │  Other Services    │
    │                 │         │  (User Service,    │
    │  - Login        │         │   Product Service, │
    │  - Register     │         │   Order Service)   │
    │  - Token Refresh│         │                    │
    │  - Validate     │         └────────────────────┘
    │  - Revoke       │
    └────────┬────────┘
             │
    ┌────────▼────────┐
    │   PostgreSQL    │
    │   (Users, Roles)│
    └─────────────────┘
    ┌─────────────────┐
    │     Redis       │
    │  (Token Cache)  │
    └─────────────────┘
```

### 2. Veritabanı Şeması

#### Users Table
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    is_active BOOLEAN DEFAULT true,
    is_verified BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_login_at TIMESTAMP,

    -- Quota limitleri (NULL = sınırsız, "*" string olarak da desteklenebilir)
    daily_query_limit INTEGER,          -- Günlük query limiti (NULL veya -1 = sınırsız)
    monthly_query_limit INTEGER,        -- Aylık query limiti
    daily_document_upload_limit INTEGER, -- Günlük belge yükleme limiti
    max_document_size_mb INTEGER DEFAULT 10, -- Maksimum belge boyutu (MB)

    -- Kullanım istatistikleri (Redis'ten periyodik sync)
    total_queries_used INTEGER DEFAULT 0,
    total_documents_uploaded INTEGER DEFAULT 0
);

-- Index'ler
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_is_active ON users(is_active);
```

#### Roles Table
```sql
CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),

    -- Rol bazlı default quota limitleri
    default_daily_query_limit INTEGER,
    default_monthly_query_limit INTEGER,
    default_daily_document_limit INTEGER,
    default_max_document_size_mb INTEGER DEFAULT 10
);

-- Örnek roller
INSERT INTO roles (name, description, default_daily_query_limit, default_monthly_query_limit, default_daily_document_limit) VALUES
('admin', 'Admin kullanıcı - sınırsız erişim', NULL, NULL, NULL),  -- NULL = sınırsız
('user', 'Normal kullanıcı', 100, 3000, 50),
('demo', 'Demo kullanıcı - sınırlı erişim', 10, 200, 5),
('guest', 'Misafir kullanıcı - çok sınırlı', 3, 30, 0);
```

#### Permissions Table
```sql
CREATE TABLE permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource VARCHAR(100) NOT NULL, -- 'research', 'documents', 'users', 'admin'
    action VARCHAR(50) NOT NULL,    -- 'query', 'upload', 'read', 'update', 'delete'
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(resource, action)
);

-- LLM servisleri için permission örnekleri
INSERT INTO permissions (resource, action, description) VALUES
('research', 'query', 'LLM sorgusu gönderme'),
('research', 'history', 'Sorgu geçmişini görüntüleme'),
('documents', 'upload', 'Belge yükleme'),
('documents', 'read', 'Belgeleri görüntüleme'),
('documents', 'delete', 'Belge silme'),
('users', 'read', 'Kullanıcı bilgilerini görüntüleme'),
('users', 'update', 'Kullanıcı bilgilerini güncelleme'),
('users', 'delete', 'Kullanıcı silme'),
('admin', '*', 'Tüm admin işlemleri');
```

#### User_Roles (Many-to-Many)
```sql
CREATE TABLE user_roles (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    role_id UUID REFERENCES roles(id) ON DELETE CASCADE,
    assigned_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, role_id)
);
```

#### Role_Permissions (Many-to-Many)
```sql
CREATE TABLE role_permissions (
    role_id UUID REFERENCES roles(id) ON DELETE CASCADE,
    permission_id UUID REFERENCES permissions(id) ON DELETE CASCADE,
    granted_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (role_id, permission_id)
);
```

#### Refresh Tokens Table
```sql
CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    revoked_at TIMESTAMP,
    device_info JSONB
);

CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_token_hash ON refresh_tokens(token_hash);
```

#### Usage History Table (PostgreSQL - Long-term storage)
```sql
CREATE TABLE usage_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    resource_type VARCHAR(50) NOT NULL, -- 'query', 'document_upload'
    action VARCHAR(50) NOT NULL,
    metadata JSONB,                     -- Query text, document name, size, etc.
    created_at TIMESTAMP DEFAULT NOW(),
    date DATE DEFAULT CURRENT_DATE      -- Günlük/aylık aggregation için
);

CREATE INDEX idx_usage_history_user_date ON usage_history(user_id, date);
CREATE INDEX idx_usage_history_resource ON usage_history(resource_type);
```

### 3. Redis Quota Tracking

Redis'te kullanıcı başına günlük ve aylık quota tracking yapılır. Her query/document upload işleminde Redis counter güncellenir.

#### Redis Key Yapısı
```
# Günlük query counter
quota:daily:query:{user_id}:{YYYY-MM-DD}  → counter (TTL: 24 saat)

# Aylık query counter
quota:monthly:query:{user_id}:{YYYY-MM}   → counter (TTL: 30 gün)

# Günlük document upload counter
quota:daily:doc:{user_id}:{YYYY-MM-DD}    → counter (TTL: 24 saat)

# Örnek:
quota:daily:query:uuid-123:2025-09-30     → 7
quota:monthly:query:uuid-123:2025-09      → 156
quota:daily:doc:uuid-123:2025-09-30       → 2
```

#### Quota Kontrolü Akışı (Research Service'ten gelen istek)

```python
# 1. Research Service'ten istek gelir
POST /research/query
Authorization: Bearer <token>

# 2. Auth Service - Quota Check
async def check_and_consume_quota(user_id: str, quota_type: str):
    # Kullanıcının limitini al (PostgreSQL'den veya cache'ten)
    user_limit = await get_user_limit(user_id, quota_type)

    # Admin check - NULL = sınırsız
    if user_limit is None:
        return {"allowed": True, "remaining": -1}  # -1 = unlimited

    # Redis'ten current usage'ı al
    today = datetime.now().strftime("%Y-%m-%d")
    redis_key = f"quota:daily:query:{user_id}:{today}"
    current_usage = await redis.get(redis_key) or 0

    # Limit kontrolü
    if current_usage >= user_limit:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Quota exceeded",
                "limit": user_limit,
                "used": current_usage,
                "reset_at": "midnight UTC"
            }
        )

    # Counter'ı artır (atomic operation)
    await redis.incr(redis_key)
    await redis.expire(redis_key, 86400)  # 24 saat TTL

    # Usage history kaydet (async, background)
    await save_usage_history(user_id, quota_type)

    return {
        "allowed": True,
        "remaining": user_limit - current_usage - 1
    }
```

#### Quota Reset (Otomatik - her gün gece yarısı)
Redis TTL ile otomatik reset olur. Manuel reset için admin endpoint:

```python
POST /api/v1/quotas/reset/{user_id}
Authorization: Bearer <admin-token>

# Redis'teki counter'ları sil
await redis.delete(f"quota:daily:query:{user_id}:{today}")
await redis.delete(f"quota:daily:doc:{user_id}:{today}")
```

### 4. JWT Token Yapısı

#### Access Token Payload
```json
{
  "sub": "user-uuid",
  "email": "user@example.com",
  "roles": ["demo"],
  "permissions": [
    {"resource": "research", "action": "query"},
    {"resource": "documents", "action": "upload"}
  ],
  "quotas": {
    "daily_query_limit": 10,
    "daily_query_remaining": 7,
    "monthly_query_limit": 200,
    "monthly_query_remaining": 156,
    "daily_document_limit": 5,
    "daily_document_remaining": 3
  },
  "iat": 1234567890,
  "exp": 1234569690,
  "type": "access"
}
```

**Not:** Quota bilgileri token'da olabilir ama **gerçek kaynak Redis'tir**. Token sadece client'a bilgi vermek için. Her istekte Redis'ten kontrol edilir.

#### Refresh Token Payload
```json
{
  "sub": "user-uuid",
  "token_id": "refresh-token-uuid",
  "iat": 1234567890,
  "exp": 1237159890,
  "type": "refresh"
}
```

### 4. API Endpoints

#### Authentication Endpoints
```
POST   /api/v1/auth/register           - Yeni kullanıcı kaydı
POST   /api/v1/auth/login              - Giriş (email/password) + quota bilgisi döner
POST   /api/v1/auth/refresh            - Token yenileme + güncel quota
POST   /api/v1/auth/logout             - Çıkış (token iptal)
POST   /api/v1/auth/verify-email       - Email doğrulama
POST   /api/v1/auth/forgot-password    - Şifre sıfırlama isteği
POST   /api/v1/auth/reset-password     - Şifre sıfırlama
GET    /api/v1/auth/me                 - Kullanıcı bilgisi + quota durumu
```

#### User Management Endpoints
```
GET    /api/v1/users/me                - Kendi bilgilerini getir
PUT    /api/v1/users/me                - Kendi bilgilerini güncelle
GET    /api/v1/users                   - Tüm kullanıcılar (admin)
GET    /api/v1/users/:id               - Kullanıcı detay (admin)
PUT    /api/v1/users/:id               - Kullanıcı güncelle (admin)
DELETE /api/v1/users/:id               - Kullanıcı sil (admin)
```

#### Role & Permission Management
```
GET    /api/v1/roles                   - Tüm roller
POST   /api/v1/roles                   - Rol oluştur (admin)
GET    /api/v1/roles/:id               - Rol detay
PUT    /api/v1/roles/:id               - Rol güncelle (admin)
DELETE /api/v1/roles/:id               - Rol sil (admin)

POST   /api/v1/roles/:id/permissions   - Role yetki ekle
DELETE /api/v1/roles/:id/permissions/:permId - Rolden yetki çıkar

POST   /api/v1/users/:id/roles         - Kullanıcıya rol ata
DELETE /api/v1/users/:id/roles/:roleId - Kullanıcıdan rol kaldır
```

#### Quota Management Endpoints
```
GET    /api/v1/quotas/me               - Kendi quota durumum
GET    /api/v1/quotas/:userId          - Kullanıcı quota durumu (admin)
POST   /api/v1/quotas/check            - Quota kontrolü (internal - servisler arası)
POST   /api/v1/quotas/consume          - Quota tüket (internal - servisler arası)
POST   /api/v1/quotas/reset/:userId    - Quota sıfırla (admin)
GET    /api/v1/quotas/usage-history    - Kullanım geçmişi
```

#### Validation Endpoint (Diğer servisler için)
```
POST   /api/v1/auth/validate           - Token doğrulama + quota kontrolü
POST   /api/v1/auth/authorize          - Yetki kontrolü
```

## İmplementasyon Adımları

### Faz 1: Temel Altyapı (Hafta 1)
1. Proje setup (FastAPI + Python 3.11+)
   - Virtual environment (venv veya poetry)
   - requirements.txt veya pyproject.toml
2. PostgreSQL ve Redis bağlantıları
   - SQLAlchemy async engine
   - Redis client (aioredis)
3. Veritabanı migration sistemi (Alembic)
4. Temel hata yönetimi ve logging
5. Environment configuration (pydantic-settings)

### Faz 2: Core Authentication (Hafta 2)
1. User model ve CRUD (SQLAlchemy)
2. Password hashing (passlib with bcrypt)
3. JWT token generation/validation (python-jose)
4. Login/Register endpoints
5. Refresh token mekanizması

### Faz 3: Authorization (Hafta 3)
1. Role ve Permission modelleri (SQLAlchemy)
2. RBAC (Role-Based Access Control) implementasyonu
3. JWT'ye permission ekleme
4. Authorization dependency (FastAPI Depends)
5. Role ve permission CRUD endpoints

### Faz 4: Gelişmiş Özellikler (Hafta 4)
1. Email verification (SMTP)
2. Password reset flow
3. 2FA (pyotp library)
4. Rate limiting (slowapi veya custom Redis)
5. Audit logging

### Faz 5: Servis Entegrasyonu (Hafta 5)
1. API Gateway setup (NGINX basit başlangıç)
2. Service-to-service authentication
3. Token validation middleware (diğer Python servisler için)
4. Diğer servislere entegrasyon örnekleri
5. Dokümantasyon (FastAPI otomatik Swagger/OpenAPI)

### Faz 6: Production Hazırlık (Hafta 6)
1. Docker containerization
2. Kubernetes deployment manifests
3. Health check endpoints
4. Monitoring ve metrics (Prometheus/Grafana)
5. Load testing ve optimization (uvicorn workers)

## Güvenlik Best Practices

### 1. Password Security
- Bcrypt ile minimum 10 round
- Password complexity gereksinimleri
- Password history tutma (son 5 şifre)

### 2. Token Security
- Access token'ı kısa tutun (15-30 dakika)
- Refresh token rotation
- Token blacklist (Redis)
- Secure cookie kullanımı (httpOnly, secure, sameSite)

### 3. Rate Limiting
- Login endpoint: 5 deneme / 15 dakika
- Register endpoint: 3 kayıt / saat / IP
- Password reset: 3 istek / saat / email

### 4. Input Validation
- Class-validator kullanımı
- SQL injection koruması (Parameterized queries)
- XSS koruması

### 5. HTTPS & CORS
- Production'da sadece HTTPS
- CORS strict configuration
- Helmet.js middleware

## Research Service Entegrasyonu

### Senaryo: Demo User Query Gönderme

```
1. Demo user login olur → 10 query hakkı var

2. Research Service'e query gönderir:
   POST /research/query
   Authorization: Bearer <token>
   Body: {"query": "Python nedir?"}

3. Research Service → Auth Service'e quota kontrolü yapar:
   POST /api/v1/quotas/check-and-consume
   Body: {
     "user_id": "uuid-123",
     "quota_type": "daily_query"
   }

4. Auth Service:
   - Redis'ten kontrol: quota:daily:query:uuid-123:2025-09-30 → 7
   - Limit: 10
   - Kalan: 10 - 7 = 3 ✅ İzin ver
   - Counter'ı artır: 7 → 8
   - Response: {"allowed": true, "remaining": 2}

5. Research Service → LLM'e query gönderir, cevap döner

---

10. query sonrası:
   Redis: quota:daily:query:uuid-123:2025-09-30 → 10

11. query gelir:
   - Counter: 10
   - Limit: 10
   - 10 >= 10 ❌ Limit aşıldı
   - Response: 429 Too Many Requests
     {
       "error": "Daily query limit exceeded",
       "limit": 10,
       "used": 10,
       "reset_at": "2025-10-01T00:00:00Z"
     }
```

## Diğer Python Servislerde Kullanım

### Option 1: JWT Validation + Quota Check Dependency (Önerilen)
Diğer Python/FastAPI servislerinizde JWT'yi validate eden ve quota kontrol eden dependency:

```python
# auth_dependency.py (Her serviste kullanılabilir)
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import os

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """JWT token'dan kullanıcı bilgisini çıkarır"""
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            os.getenv("JWT_SECRET"),
            algorithms=["HS256"]
        )
        return {
            "user_id": payload.get("sub"),
            "email": payload.get("email"),
            "roles": payload.get("roles", []),
            "permissions": payload.get("permissions", [])
        }
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )

def require_permission(resource: str, action: str):
    """Belirli bir permission gerektiren dependency"""
    async def permission_checker(user: dict = Depends(get_current_user)):
        # Admin her şeyi yapabilir
        if "admin" in user["roles"]:
            return user

        # Permission kontrolü
        has_permission = any(
            p["resource"] == resource and p["action"] == action
            for p in user["permissions"]
        )

        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )

        return user

    return permission_checker

# Kullanım - Product Service
from fastapi import FastAPI
from auth_dependency import get_current_user, require_permission

app = FastAPI()

@app.get("/products")
async def get_products(
    user: dict = Depends(require_permission("products", "read"))
):
    # user otomatik olarak dolu gelir
    return {"products": [...]}

@app.post("/products")
async def create_product(
    product_data: dict,
    user: dict = Depends(require_permission("products", "create"))
):
    # Sadece yetkili kullanıcılar buraya girebilir
    return {"created": True}

@app.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    # Sadece login olmuş kullanıcılar
    return user

# Research Service için Quota Check
import httpx

async def check_quota(user_id: str, quota_type: str):
    """Auth Service'e quota kontrolü yapar"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://auth-service:8000/api/v1/quotas/check-and-consume",
            json={"user_id": user_id, "quota_type": quota_type},
            headers={"X-Internal-Service": "research-service"}  # Internal auth
        )
        if response.status_code == 429:
            raise HTTPException(
                status_code=429,
                detail=response.json()
            )
        return response.json()

# Research endpoint with quota check
@app.post("/research/query")
async def research_query(
    query: str,
    user: dict = Depends(get_current_user)
):
    # 1. Quota kontrolü
    quota_result = await check_quota(user["user_id"], "daily_query")

    # 2. LLM'e query gönder
    llm_response = await send_to_llm(query)

    return {
        "response": llm_response,
        "quota_remaining": quota_result["remaining"]
    }
```

### Option 2: Gateway Seviyesinde Validation
API Gateway'de JWT validation yapılır, microservice'lere kullanıcı bilgisi header ile gönderilir.

```
Client -> API Gateway (JWT Validate) -> Microservice (X-User-Id header)
```

### Paylaşılan Auth Utils Package (Önerilen)
Tüm servisler için ortak bir package:

```bash
# Dizin yapısı
common-auth-utils/
├── setup.py
├── auth_utils/
│   ├── __init__.py
│   ├── dependencies.py  # FastAPI dependencies
│   └── jwt_helper.py    # JWT validate fonksiyonları

# Her serviste:
pip install -e ../common-auth-utils
```

## Persona Örnekleri

### 1. Admin Persona
```json
{
  "role": "admin",
  "permissions": [
    {"resource": "*", "action": "*"}
  ],
  "quotas": {
    "daily_query_limit": null,          // null = sınırsız
    "monthly_query_limit": null,
    "daily_document_limit": null,
    "max_document_size_mb": 100
  },
  "description": "Sistem yöneticisi - sınırsız erişim"
}
```

### 2. User Persona (Normal Kullanıcı)
```json
{
  "role": "user",
  "permissions": [
    {"resource": "research", "action": "query"},
    {"resource": "research", "action": "history"},
    {"resource": "documents", "action": "upload"},
    {"resource": "documents", "action": "read"},
    {"resource": "documents", "action": "delete"},
    {"resource": "users", "action": "read", "condition": "self"},
    {"resource": "users", "action": "update", "condition": "self"}
  ],
  "quotas": {
    "daily_query_limit": 100,
    "monthly_query_limit": 3000,
    "daily_document_limit": 50,
    "max_document_size_mb": 10
  },
  "description": "Normal kullanıcı - günlük 100 sorgu, aylık 3000 sorgu"
}
```

### 3. Demo Persona
```json
{
  "role": "demo",
  "permissions": [
    {"resource": "research", "action": "query"},
    {"resource": "research", "action": "history"},
    {"resource": "documents", "action": "upload"},
    {"resource": "documents", "action": "read"},
    {"resource": "users", "action": "read", "condition": "self"}
  ],
  "quotas": {
    "daily_query_limit": 10,            // Günde sadece 10 sorgu
    "monthly_query_limit": 200,
    "daily_document_limit": 5,          // Günde 5 belge
    "max_document_size_mb": 5
  },
  "description": "Demo kullanıcı - sınırlı deneme erişimi",
  "limitations": [
    "Günde maksimum 10 sorgu",
    "Belge silme yapamaz",
    "Admin işlemleri yapamaz"
  ]
}
```

### 4. Guest Persona
```json
{
  "role": "guest",
  "permissions": [
    {"resource": "research", "action": "query"}
  ],
  "quotas": {
    "daily_query_limit": 3,             // Günde sadece 3 sorgu
    "monthly_query_limit": 30,
    "daily_document_limit": 0,          // Belge yükleyemez
    "max_document_size_mb": 0
  },
  "description": "Kayıt olmamış misafir - çok sınırlı erişim"
}
```

## Ölçeklendirme Stratejileri

### Horizontal Scaling
- Auth service'i stateless tutun
- Redis cluster için session/cache
- Load balancer arkasında multiple instance

### Database Optimization
- Connection pooling
- Read replicas (read-heavy operations için)
- Index optimization (email, user_id, role_id)

### Caching Strategy
- User permissions cache (Redis - 5 dakika TTL)
- Public key cache (JWT verification için)
- Rate limit counters (Redis)

### Monitoring
- Token generation/validation metrics
- Failed login attempts tracking
- API response times
- Database query performance

## Deployment

### Docker Compose (Development)
```yaml
version: '3.8'
services:
  auth-service:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/auth
      - REDIS_URL=redis://redis:6379
      - JWT_SECRET=your-secret-key-change-in-production
      - JWT_ALGORITHM=HS256
      - ACCESS_TOKEN_EXPIRE_MINUTES=30
      - REFRESH_TOKEN_EXPIRE_DAYS=7
    depends_on:
      - postgres
      - redis
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: auth
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

### Kubernetes (Production)
- Deployment: 3+ replicas
- HPA (Horizontal Pod Autoscaler)
- Secret management (Vault/Sealed Secrets)
- Ingress with TLS
- PersistentVolumes for database

## Python/FastAPI Proje Yapısı

```
onedocs-auth/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app
│   ├── config.py                  # Settings (pydantic-settings)
│   ├── database.py                # DB connection, session
│   ├── dependencies.py            # Global dependencies
│   │
│   ├── models/                    # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── role.py
│   │   ├── permission.py
│   │   └── refresh_token.py
│   │
│   ├── schemas/                   # Pydantic schemas (request/response)
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── auth.py
│   │   ├── role.py
│   │   └── permission.py
│   │
│   ├── crud/                      # Database operations
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── role.py
│   │   └── permission.py
│   │
│   ├── api/                       # API routes
│   │   ├── __init__.py
│   │   ├── deps.py                # Auth dependencies
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── auth.py            # Login, register, refresh
│   │       ├── users.py           # User CRUD
│   │       ├── roles.py           # Role CRUD
│   │       └── permissions.py     # Permission CRUD
│   │
│   ├── core/                      # Core utilities
│   │   ├── __init__.py
│   │   ├── security.py            # JWT, password hashing
│   │   ├── config.py              # Environment config
│   │   └── redis.py               # Redis client
│   │
│   └── middleware/                # Custom middleware
│       ├── __init__.py
│       ├── rate_limit.py
│       └── logging.py
│
├── alembic/                       # Database migrations
│   ├── versions/
│   └── env.py
│
├── tests/                         # Tests
│   ├── __init__.py
│   ├── conftest.py
│   └── test_auth.py
│
├── .env                           # Environment variables
├── .env.example
├── requirements.txt               # Dependencies
├── Dockerfile
├── docker-compose.yml
├── alembic.ini                    # Alembic config
└── README.md
```

## Python Dependencies (requirements.txt)

```txt
# FastAPI
fastapi==0.109.0
uvicorn[standard]==0.27.0
pydantic==2.5.0
pydantic-settings==2.1.0

# Database
sqlalchemy==2.0.25
asyncpg==0.29.0
alembic==1.13.1

# Redis
redis==5.0.1
aioredis==2.0.1

# Authentication
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.6

# Security
bcrypt==4.1.2

# Email (optional)
fastapi-mail==1.4.1

# 2FA (optional)
pyotp==2.9.0

# Rate limiting
slowapi==0.1.9

# Validation
email-validator==2.1.0

# Testing
pytest==7.4.4
pytest-asyncio==0.23.3
httpx==0.26.0
```

## Sonuç

Bu mimari:
- ✅ Ölçeklenebilir (horizontal scaling, async/await)
- ✅ Güvenli (JWT, bcrypt, rate limiting)
- ✅ Performanslı (Redis cache, stateless, async)
- ✅ Maintainable (modüler yapı, type hints)
- ✅ Production-ready (monitoring, logging, health checks)
- ✅ Diğer Python servislerinizle uyumlu

Başlangıç için FastAPI + PostgreSQL + Redis kombinasyonu ile başlayın. İlk 2 haftada core authentication'ı tamamlayın, sonra authorization ve advanced features'a geçin.
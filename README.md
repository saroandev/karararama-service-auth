# OneDocs Auth Service

LLM tabanlı Research servisi için merkezi authentication ve authorization sistemi.

## 🚀 Özellikler

- **FastAPI** backend framework
- **PostgreSQL** veritabanı (async SQLAlchemy)
- **JWT** token tabanlı authentication
- **RBAC** (Role-Based Access Control) yetkilendirme
- **Quota Management** - Kullanıcı bazlı günlük/aylık sorgu limitleri
- **pgAdmin** - Database yönetim arayüzü

## 📋 Gereksinimler

- Python 3.9+
- Docker & Docker Compose
- PostgreSQL 15

## 🛠️ Kurulum

### 1. Repository'yi klonlayın

```bash
git clone <repo-url>
cd onedocs-auth
```

### 2. Virtual environment oluşturun

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# veya
venv\Scripts\activate  # Windows
```

### 3. Bağımlılıkları yükleyin

```bash
pip install -r requirements.txt
```

### 4. Environment variables ayarlayın

```bash
cp .env.example .env
# .env dosyasını düzenleyin
```

### 5. PostgreSQL ve pgAdmin'i başlatın

```bash
docker compose up -d
```

### 6. Database migration'larını çalıştırın

```bash
alembic upgrade head
```

## 🗄️ pgAdmin Kullanımı

pgAdmin'e erişmek için:

1. Tarayıcınızda açın: **http://localhost:5050**
2. Login bilgileri (`.env` dosyasından):
   - Email: `admin@onedocs.com`
   - Password: `admin123`

### PostgreSQL Server Ekleme

pgAdmin'de yeni server ekleyin:

1. **Servers** → **Create** → **Server**
2. **General** tab:
   - Name: `OneDocs Auth`
3. **Connection** tab:
   - Host name/address: `postgres` (Docker network içinde)
   - Port: `5432` (container içi port)
   - Maintenance database: `onedocs_auth`
   - Username: `onedocs_user`
   - Password: `onedocs_pass_2024`
4. **Save**

## 📊 Database Yapısı

### Tablolar

- `users` - Kullanıcı bilgileri ve quota limitleri
- `roles` - Kullanıcı rolleri (admin, user, demo, guest)
- `permissions` - İzinler (resource:action formatında)
- `refresh_tokens` - JWT refresh token'ları
- `user_roles` - User-Role ilişkisi (many-to-many)
- `role_permissions` - Role-Permission ilişkisi (many-to-many)

### Roller ve Quota Limitleri

| Role  | Daily Query | Monthly Query | Daily Docs | Description |
|-------|-------------|---------------|------------|-------------|
| admin | ∞ (NULL)    | ∞ (NULL)      | ∞ (NULL)   | Sınırsız erişim |
| user  | 100         | 3000          | 50         | Normal kullanıcı |
| demo  | 10          | 200           | 5          | Demo kullanıcı |
| guest | 3           | 30            | 0          | Misafir |

## 🔧 Geliştirme

### Yeni Migration Oluşturma

```bash
alembic revision --autogenerate -m "migration_message"
```

### Migration Uygulama

```bash
alembic upgrade head
```

### Migration Geri Alma

```bash
alembic downgrade -1
```

## 🐳 Docker Komutları

```bash
# Container'ları başlat
docker compose up -d

# Container'ları durdur
docker compose down

# Logları görüntüle
docker compose logs -f

# PostgreSQL'e bağlan
docker exec -it onedocs-auth-db psql -U onedocs_user -d onedocs_auth
```

## 📝 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_HOST` | PostgreSQL host | localhost |
| `POSTGRES_PORT` | PostgreSQL port | 5441 |
| `POSTGRES_USER` | Database kullanıcı | onedocs_user |
| `POSTGRES_PASSWORD` | Database şifre | - |
| `POSTGRES_DB` | Database adı | onedocs_auth |
| `JWT_SECRET_KEY` | JWT secret key | - |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token süresi | 30 |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token süresi | 7 |
| `PGADMIN_DEFAULT_EMAIL` | pgAdmin email | admin@onedocs.com |
| `PGADMIN_DEFAULT_PASSWORD` | pgAdmin şifre | admin123 |
| `PGADMIN_PORT` | pgAdmin port | 5050 |

## 📂 Proje Yapısı

```
onedocs-auth/
├── app/
│   ├── api/v1/          # API endpoints
│   ├── core/            # Config, database
│   ├── models/          # SQLAlchemy models
│   ├── schemas/         # Pydantic schemas
│   ├── crud/            # Database operations
│   └── middleware/      # Custom middleware
├── alembic/             # Database migrations
├── tests/               # Tests
├── .env                 # Environment variables
├── docker-compose.yml   # Docker services
├── requirements.txt     # Python dependencies
└── README.md
```

## 🧪 Testing

```bash
pytest
```

## 📄 Lisans

MIT

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
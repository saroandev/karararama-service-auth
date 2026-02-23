# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OneDocs Auth Service is a centralized JWT-based authentication and authorization microservice for the OneDocs ecosystem. It provides user management, RBAC (Role-Based Access Control), fine-grained permissions, quota management, and usage tracking for other services (OCR, RAG, LLM, Crawler).

**Tech Stack:** FastAPI, SQLAlchemy (async), PostgreSQL, Alembic, Python-JOSE, Passlib/Bcrypt

## Development Commands

### Environment Setup
```bash
# Local development setup (run once)
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env: Set POSTGRES_HOST=localhost for local Python dev
# Generate JWT_SECRET_KEY: openssl rand -hex 32

# Start PostgreSQL in Docker
docker compose up -d postgres

# Run migrations
alembic upgrade head

# Seed database (creates roles, permissions, default org, admin user)
python app/db_seed.py

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
# Or: ./start.sh
```

### Database Operations
```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Check current migration status
alembic current

# View migration history
alembic history
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/integration/test_auth.py

# Run by marker
pytest -m unit
pytest -m integration
```

### Docker Operations
```bash
# Start all services (postgres, pgadmin, auth-service)
docker compose up -d

# Rebuild and restart auth service
docker compose build auth-service
docker compose up -d auth-service

# View logs
docker compose logs -f auth-service

# Stop all services
docker compose down
```

### Utility Scripts
```bash
# List all users
python list_users.py

# Reset user password
python reset_password.py

# Sync user roles with organization
python sync_user_roles_org.py

# Create default organization (required for first setup)
python create_default_org.py
```

## Architecture

### Core Components

**Authentication Flow:**
- JWT-based with access tokens (30 min) and refresh tokens (7 days)
- Access tokens stored in `blacklisted_tokens` table upon logout
- Token validation via `get_current_user()` dependency in `app/api/deps.py`
- Password hashing using bcrypt via `PasswordHandler` in `app/core/security.py`

**Authorization System:**
- RBAC with many-to-many user-role relationship via `user_roles` table
- Fine-grained permissions in `resource:action` format (e.g., `research:query`, `documents:upload`)
- Wildcard support: `*:*` (full access), `resource:*`, `*:action`
- Hierarchy: `superuser` > `admin` > role-based permissions
- Authorization helpers: `require_role()` and `require_permission()` in `app/api/deps.py`

**Database Models:**
- `User`: Email, password_hash, quotas, usage stats, organization_id
- `Role`: Name, description, default quotas, permissions relationship
- `Permission`: Resource, action, description
- `Organization`: Multi-tenancy support
- `RefreshToken`: Token storage with expiration
- `BlacklistedToken`: Revoked access tokens (logout)
- `UsageLog`: Service usage tracking for quota enforcement

**Quota System:**
- User quotas: `daily_query_limit`, `monthly_query_limit`, `daily_document_upload_limit`, `max_document_size_mb`
- `NULL` values = unlimited (for admin/superuser)
- Usage tracked in `usage_logs` table via `/api/v1/usage/consume` endpoint
- Other services call this endpoint to record consumption and check quotas

### API Structure

All endpoints use `/api/v1` prefix:

- `/auth` - Register, login, token verify (inter-service), logout, password reset
- `/users` - User profile management, list users (admin)
- `/admin` - Role/permission management, quota updates
- `/usage` - Consumption tracking, usage statistics
- `/organizations` - Organization CRUD (multi-tenancy)

**Inter-Service Integration:**
- `POST /api/v1/auth/verify` - Other services validate tokens and get user context
- `POST /api/v1/usage/consume` - Other services report usage and check quotas
- Returns 429 when quota exceeded with reset time

### Key Implementation Details

**Registration Flow (app/api/v1/auth.py):**
- `full_name` is automatically split into `first_name` and `last_name`
- Password minimum 6 characters, must match `password_confirm`
- User assigned `guest` role by default
- User must be assigned organization and proper role by admin before full access

**Login Requirements:**
- User must have `is_active=True`
- User credentials validated via `verify_password()`
- Returns access token + refresh token

**Token Blacklisting:**
- On logout, access token added to `blacklisted_tokens` table
- `get_current_user()` checks blacklist before validating token
- Prevents reuse of logged-out tokens

**Password Reset Flow (app/api/v1/auth.py):**
- Token-based reset (email contains reset link with secure token)
- Tokens expire after 30 minutes (configurable)
- Rate limit: 3 requests per hour per user
- Single-use tokens (marked as used after password reset)
- All user sessions terminated after successful password reset
- Endpoints:
  - `POST /api/v1/auth/forgot-password` - Request password reset email
  - `POST /api/v1/auth/validate-reset-token` - Validate token before showing form
  - `POST /api/v1/auth/reset-password` - Reset password with token
- Security features:
  - Generic success messages (prevent email enumeration)
  - SHA256 hashed tokens in database
  - Token cannot be reused
  - All refresh tokens revoked on password reset
  - Rate limiting per user account

**Role Hierarchy (app/db_seed.py):**
- `superuser` - Full system control
- `admin` - Unlimited access, user management
- `premium` - 500 daily queries, 15000 monthly, advanced features
- `user` - 100 daily queries, 3000 monthly, standard features
- `demo` - 10 daily queries, 200 monthly, limited access
- `guest` - 3 daily queries, 30 monthly, minimal access

**Database Seeding:**
- `app/db_seed.py` creates all roles, permissions, default organization, and admin user
- Default admin: `admin@onedocs.com` / `admin123` (must change on first login)
- Run via `python app/db_seed.py` after migrations

**Configuration (app/core/config.py):**
- Settings loaded from `.env` using `pydantic-settings`
- Key settings: `DATABASE_URL`, `JWT_SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `CORS_ORIGINS`
- Password reset settings: `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES`, `PASSWORD_RESET_RATE_LIMIT_REQUESTS`, `FRONTEND_RESET_PASSWORD_URL`
- `POSTGRES_HOST`: Use `localhost` for local Python dev, `postgres` for Docker Compose

**Testing Setup (conftest.py):**
- Uses SQLite (`test.db`) for tests, not PostgreSQL
- Fixtures: `test_user`, `admin_user`, `test_role`, `admin_role`, `test_permission`
- Token fixtures: `test_access_token`, `admin_access_token`
- Header fixtures: `auth_headers`, `admin_auth_headers`
- Test markers: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.auth`

## Important Patterns

**Async Database Sessions:**
- All CRUD operations use async SQLAlchemy
- Use `get_db()` dependency for endpoint database access
- Example: `async def endpoint(db: AsyncSession = Depends(get_db))`

**CRUD Pattern:**
- All database operations in `app/crud/` modules
- Base CRUD class in `app/crud/base.py` with common operations
- Specialized methods in model-specific CRUD classes

**Dependency Injection for Auth:**
```python
# Require authentication
user: User = Depends(get_current_active_user)

# Require specific role
user: User = Depends(require_role(["admin"]))

# Require specific permission
user: User = Depends(require_permission("research", "query"))
```

**Migration Naming:**
- Format: `YYYYMMDD_HHMM-revision_slug`
- Example: `20251024_1711-9c7e8cba487b_create_blacklisted_tokens_table`
- Configured in `alembic.ini` via `file_template`

## Common Development Tasks

**Adding New Permission:**
1. Add to `permissions_data` in `app/db_seed.py`
2. Assign to appropriate roles in `roles_data`
3. Run `python app/db_seed.py` to update database

**Creating New Endpoint:**
1. Add route in appropriate file under `app/api/v1/`
2. Use `Depends(get_current_active_user)` for authenticated endpoints
3. Use `require_role()` or `require_permission()` for authorization
4. Add router to `app/api/v1/__init__.py` if new module

**Adding Model Field:**
1. Update model in `app/models/`
2. Update schema in `app/schemas/`
3. Run `alembic revision --autogenerate -m "add_field_name"`
4. Review generated migration, then `alembic upgrade head`

**User Email as Identifier:**
- Recent changes use `user_email` instead of `user_id` for organization assignments
- Recent changes use `role_name` instead of `role_id` for role operations
- Check recent commits for these patterns when working with user/role endpoints

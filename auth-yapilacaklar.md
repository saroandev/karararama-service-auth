# Auth Servisi - Yapılacaklar Listesi

Bu dosya OneDocs Auth Servisi için tespit edilen eksiklikleri ve geliştirilmesi gereken özellikleri içerir.

---

## 🔴 Kritik Öncelikli (Hemen Yapılmalı)

### 1. Email Verification Sistemi
**Durum:** ❌ Eksik
**Açıklama:** Model'de `is_verified` field var ama kullanılmıyor.

**Yapılacaklar:**
- [ ] Email verification token tablosu oluştur
- [ ] `POST /api/v1/auth/send-verification-email` endpoint'i ekle
- [ ] `POST /api/v1/auth/verify-email?token=xxx` endpoint'i ekle
- [ ] Email gönderim servisi entegrasyonu (SMTP/SendGrid)
- [ ] Verification email template'i hazırla
- [ ] Register sonrası otomatik email gönderimi

**İlgili Dosyalar:**
- `app/models/user.py:56` - `is_verified` field
- Yeni: `app/models/verification_token.py`
- Yeni: `app/api/v1/auth.py` - verification endpoints

---

### 2. Password Reset / Forgot Password
**Durum:** ❌ Eksik
**Açıklama:** Şifre sıfırlama mekanizması yok.

**Yapılacaklar:**
- [ ] Password reset token tablosu oluştur
- [ ] `POST /api/v1/auth/forgot-password` endpoint'i (email gönder)
- [ ] `POST /api/v1/auth/reset-password` endpoint'i (token ile şifre değiştir)
- [ ] Reset email template'i hazırla
- [ ] Token expiration (15-30 dakika)
- [ ] Rate limiting (aynı email'e 5 dk'da 1 istek)

**İlgili Dosyalar:**
- Yeni: `app/models/password_reset_token.py`
- `app/api/v1/auth.py` - reset endpoints
- `app/crud/user.py` - password update metodu

---

### 3. Rate Limiting / Brute-Force Protection
**Durum:** ❌ Eksik
**Açıklama:** Login brute-force saldırılarına karşı korumasız.

**Yapılacaklar:**
- [ ] Rate limiting middleware ekle (slowapi/redis)
- [ ] Login endpoint'ine rate limit (IP bazlı: 5/dakika)
- [ ] Başarısız login denemelerini kaydet
- [ ] 5 başarısız denemeden sonra hesap kilitleme (15 dk)
- [ ] CAPTCHA entegrasyonu (opsiyonel)

**İlgili Dosyalar:**
- Yeni: `app/middleware/rate_limit.py`
- `app/api/v1/auth.py:56` - login endpoint
- Yeni: `app/models/failed_login_attempt.py`

---

### 4. Refresh Token Cleanup Task
**Durum:** ⚠️ Yarım
**Açıklama:** CRUD'da `cleanup_expired()` var ama çağıran background task yok.

**Yapılacaklar:**
- [ ] Background task sistemi ekle (APScheduler/Celery)
- [ ] Günlük cleanup job'ı oluştur (her gece 03:00)
- [ ] Expired/revoked token'ları sil
- [ ] Cleanup log kayıtları

**İlgili Dosyalar:**
- `app/crud/refresh_token.py:131` - cleanup_expired metodu
- Yeni: `app/tasks/cleanup_tokens.py`
- Yeni: `app/core/scheduler.py`

---

### 5. Access Token Blacklist Sistemi
**Durum:** ❌ Eksik
**Açıklama:** Logout sonrası access token 30 dakika boyunca hala geçerli.

**Yapılacaklar:**
- [ ] Redis blacklist implementasyonu
- [ ] Logout'ta access token'ı blacklist'e ekle
- [ ] Token validation'da blacklist kontrolü
- [ ] TTL ile otomatik temizlik (30 dakika)
- [ ] Acil durum token iptali endpoint'i (admin)

**İlgili Dosyalar:**
- Yeni: `app/core/redis.py`
- `app/api/deps.py:21` - get_current_user (blacklist kontrolü ekle)
- `app/api/v1/auth.py:305` - logout endpoint

---

## 🟡 Orta Öncelikli (Kısa Vadede Yapılmalı)

### 6. Audit Log / Activity Tracking
**Durum:** ❌ Eksik
**Açıklama:** Kullanıcı aktiviteleri kaydedilmiyor.

**Yapılacaklar:**
- [ ] Audit log tablosu oluştur
- [ ] Login/logout kayıtları
- [ ] Başarısız login denemeleri
- [ ] IP adresi ve user agent tracking
- [ ] Şifre değişikliği kayıtları
- [ ] Admin aktiviteleri (rol atama vb.)
- [ ] Audit log görüntüleme endpoint'i

**İlgili Dosyalar:**
- Yeni: `app/models/audit_log.py`
- Yeni: `app/crud/audit_log.py`
- Yeni: `app/api/v1/admin.py` - audit log endpoints

---

### 7. Password Policy Validation
**Durum:** ❌ Eksik
**Açıklama:** Şifre karmaşıklık kuralları yok.

**Yapılacaklar:**
- [ ] Minimum uzunluk kontrolü (en az 8 karakter)
- [ ] En az 1 büyük harf zorunluluğu
- [ ] En az 1 küçük harf zorunluluğu
- [ ] En az 1 rakam zorunluluğu
- [ ] En az 1 özel karakter zorunluluğu
- [ ] Yaygın şifreleri blacklist (123456, password vb.)
- [ ] Şifre tekrar kullanım kontrolü (son 5 şifre)

**İlgili Dosyalar:**
- Yeni: `app/core/password_validator.py`
- `app/schemas/user.py` - UserCreate validator
- `app/api/v1/auth.py` - register/reset endpoints

---

### 8. Session Management UI
**Durum:** ⚠️ Yarım
**Açıklama:** Tek oturum var ama kullanıcı göremiyor.

**Yapılacaklar:**
- [ ] Aktif oturumları listeleme endpoint'i
- [ ] Oturum detayları (cihaz, IP, son aktivite)
- [ ] Oturumu sonlandırma (current session hariç)
- [ ] Tüm oturumları sonlandırma (security breach durumu)

**İlgili Dosyalar:**
- `app/models/refresh_token.py:70` - device_info field (şu an null)
- `app/api/v1/users.py` - session management endpoints
- `app/crud/refresh_token.py` - session queries

---

### 9. Response Model Standardizasyonu
**Durum:** ⚠️ Inconsistent
**Açıklama:** API response'ları farklı formatlar kullanıyor.

**Yapılacaklar:**
- [ ] Standart response wrapper oluştur
- [ ] Başarılı response formatı: `{success: true, data: {...}}`
- [ ] Hata response formatı: `{success: false, error: {...}}`
- [ ] HTTP status code standartları
- [ ] Error code enumerations
- [ ] Validation error format standardizasyonu

**İlgili Dosyalar:**
- Yeni: `app/schemas/common.py` - BaseResponse
- Tüm endpoint'ler güncellenecek

---

### 10. Logging Sistemi
**Durum:** ❌ Eksik
**Açıklama:** Structured logging ve error tracking yok.

**Yapılacaklar:**
- [ ] Structured logging setup (loguru/structlog)
- [ ] Log levels (DEBUG, INFO, WARNING, ERROR)
- [ ] Request/response logging
- [ ] Error tracking entegrasyonu (Sentry)
- [ ] Log rotation ve retention policy
- [ ] Performance logging (slow queries)

**İlgili Dosyalar:**
- Yeni: `app/core/logging.py`
- `app/main.py` - logging middleware
- `.env` - log level configuration

---

## 🟢 Uzun Vadeli (Nice to Have)

### 11. Two-Factor Authentication (2FA)
**Durum:** ❌ Eksik

**Yapılacaklar:**
- [ ] TOTP (Time-based OTP) implementasyonu
- [ ] QR code generation (Google Authenticator)
- [ ] Backup codes
- [ ] SMS OTP (Twilio entegrasyonu)
- [ ] 2FA enable/disable endpoints
- [ ] Recovery mechanism

**İlgili Dosyalar:**
- Yeni: `app/models/two_factor.py`
- Yeni: `app/api/v1/auth.py` - 2FA endpoints
- Yeni: `app/core/totp.py`

---

### 12. API Key Management
**Durum:** ❌ Eksik
**Açıklama:** Servisler arası long-lived token sistemi yok.

**Yapılacaklar:**
- [ ] API key tablosu oluştur
- [ ] API key generation endpoint
- [ ] API key rotation
- [ ] Scope/permission bazlı API keys
- [ ] API key usage tracking
- [ ] API key revocation

**İlgili Dosyalar:**
- Yeni: `app/models/api_key.py`
- Yeni: `app/api/v1/api_keys.py`
- `app/api/deps.py` - API key authentication

---

### 13. Metrics & Monitoring
**Durum:** ❌ Eksik

**Yapılacaklar:**
- [ ] Prometheus metrics export
- [ ] Request count, latency metrics
- [ ] Database connection pool metrics
- [ ] Custom business metrics (daily active users)
- [ ] Grafana dashboard template
- [ ] Health check detayları (DB, Redis connectivity)

**İlgili Dosyalar:**
- Yeni: `app/middleware/metrics.py`
- `app/main.py:33` - health check endpoint (detaylandır)
- Yeni: `prometheus/grafana-dashboard.json`

---

### 14. Advanced Security Features

**Yapılacaklar:**
- [ ] HTTPS enforcement (production)
- [ ] Secure cookie flags (HttpOnly, Secure, SameSite)
- [ ] HSTS headers
- [ ] CSP (Content Security Policy) headers
- [ ] SQL injection protection (zaten var ✅ - parameterized queries)
- [ ] XSS protection headers
- [ ] Account takeover detection (suspicious login patterns)
- [ ] Device fingerprinting

---

### 15. OAuth2 / Social Login
**Durum:** ❌ Eksik

**Yapılacaklar:**
- [ ] Google OAuth2
- [ ] GitHub OAuth2
- [ ] Microsoft OAuth2
- [ ] Social account linking
- [ ] Profile data sync

---

### 16. Multi-tenancy Support
**Durum:** ❌ Eksik

**Yapılacaklar:**
- [ ] Organization/Tenant model
- [ ] Tenant isolation
- [ ] Tenant-specific permissions
- [ ] Cross-tenant admin

---

### 17. Advanced Usage Tracking
**Durum:** ⚠️ Temel var

**Geliştirmeler:**
- [ ] Real-time quota tracking (Redis)
- [ ] Kullanım grafikler/analytics
- [ ] Quota uyarı bildirimleri
- [ ] Custom quota packages
- [ ] Kullanım raporu export (CSV/PDF)

**İlgili Dosyalar:**
- `app/models/usage_log.py` - mevcut
- `app/api/v1/usage.py` - genişletilecek

---

## 📊 Önceliklendirme Önerisi

### Sprint 1 (1-2 Hafta)
- ✅ Refresh Token DB Integration (Tamamlandı)
- 🔴 Password Reset/Forgot Password
- 🔴 Email Verification
- 🔴 Rate Limiting

### Sprint 2 (1-2 Hafta)
- 🔴 Refresh Token Cleanup Task
- 🔴 Access Token Blacklist
- 🟡 Password Policy Validation
- 🟡 Audit Logging

### Sprint 3 (1-2 Hafta)
- 🟡 Session Management UI
- 🟡 Response Standardization
- 🟡 Structured Logging
- Health Check İyileştirmeleri

### Sprint 4+ (Sonrası)
- 🟢 2FA
- 🟢 API Key Management
- 🟢 OAuth2 / Social Login
- 🟢 Metrics & Monitoring
- 🟢 Multi-tenancy

---

## 📝 Notlar

- **Redis Dependency:** Access token blacklist, rate limiting ve real-time quota tracking için Redis gerekli
- **Email Service:** Email verification ve password reset için SMTP/SendGrid entegrasyonu gerekli
- **Background Tasks:** Cleanup ve scheduled jobs için APScheduler veya Celery gerekli
- **Testing:** Her yeni özellik için unit ve integration testler yazılmalı

---

**Son Güncelleme:** 2025-10-03
**Versiyonlama:** Auth servisi şu an v1.0.0, bu özellikler v1.1.0, v1.2.0, v2.0.0 release'lerinde gelecek

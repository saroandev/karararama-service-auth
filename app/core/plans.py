"""
Plan catalog and billing constants.

Pricing model: Yıllık TRY (KDV hariç) per user. Mevcut "USD per user per
month" modeli kaldırıldı çünkü FE artık sabit TRY etiketleri gösteriyor ve
USD/TRY kuru tahsilat anında değişince frontend ile backend tutarsız oluyordu.

Tahsilat hesabı:
    paket_tutari = price_try_per_user_yearly * seat_count
    addon_tutari = ARCHIVE_ADDON_PRICE_TRY (eğer checkbox)
    ara_toplam   = paket_tutari + addon_tutari
    indirim      = ara_toplam * (discount_percent / 100)  (uygulandıysa)
    net          = ara_toplam - indirim
    kdv          = net * (VAT_PERCENT / 100)
    toplam       = net + kdv

PayTR'a `toplam` kuruş cinsinden gider (`amount_kurus`).

Billing cycle: artık sadece "yearly". `sixmonth` desteği geçici olarak
çıkarıldı (kullanılmıyordu); ileride lazım olursa BILLING_CYCLES'a tekrar
eklenebilir, hesap formülü değişmiyor.
"""
from typing import Optional, TypedDict


class PlanDefinition(TypedDict):
    name: str
    min_users: int
    max_users: Optional[int]                  # None = unlimited (Enterprise)
    price_try_per_user_yearly: int            # TRY, KDV hariç
    storage_gb_per_user: float
    contact_sales_only: bool


# `contact_sales_only`:
#   True  → frontend "Sizi arayalım" gösterir, /odeme akışı kapalı; backend
#           /billing/orders bu plan için 400 döner (sadece Enterprise).
#   False → /odeme akışı açık (PayTR ile self-service satın alma).
PLAN_CATALOG: dict[str, PlanDefinition] = {
    "solo": {
        "name": "Solo",
        "min_users": 1,
        "max_users": 1,
        # 2026 lansman: liste fiyatı ₺40.000, %50 indirim → ₺20.000 KDV haric.
        "price_try_per_user_yearly": 20000,
        "storage_gb_per_user": 1.0,
        "contact_sales_only": False,
    },
    "team": {
        "name": "Team",
        "min_users": 2,
        "max_users": 9,
        # 2026 lansman: liste fiyatı ₺36.000, %50 indirim → ₺18.000 KDV haric.
        "price_try_per_user_yearly": 18000,
        "storage_gb_per_user": 5.0,
        "contact_sales_only": False,
    },
    "elite": {
        "name": "Elite",
        "min_users": 10,
        "max_users": 49,
        # 2026 lansman: liste fiyatı ₺30.000, %50 indirim → ₺15.000 KDV haric.
        "price_try_per_user_yearly": 15000,
        "storage_gb_per_user": 7.5,
        "contact_sales_only": False,
    },
    "enterprise": {
        "name": "Enterprise",
        "min_users": 50,
        "max_users": None,
        "price_try_per_user_yearly": 0,       # fiyat görüşülür
        "storage_gb_per_user": 10.0,
        "contact_sales_only": True,
    },
}

# 2026 itibariyle aktif tek billing cycle.
BILLING_CYCLES = {
    "yearly": 12,
}

# Paid plans (post-trial) — quota dependencies bunu kullanır.
PAID_PLANS = {"solo", "team", "elite", "enterprise"}

# Whitelabel slug (<slug>.onedocs.ai) bu planlarda aktif.
WHITELABEL_PLANS = {"elite", "enterprise"}

# Plan states
PLAN_FREE_TRIAL = "free_trial"
PLAN_EXPIRED_TRIAL = "expired_trial"
PLAN_EXPIRED_SUBSCRIPTION = "expired_subscription"

# Trial duration — 24 saat. Mevcut user'ların trial_ends_at değerleri
# DB'de zaten yazılı olduğu için migration sırasında DOKUNMUYORUZ; sadece
# yeni kayıtlar 1 günlük trial alır.
TRIAL_DURATION_DAYS = 1

# KDV oranı (%) — FE'de gösterim ve backend hesabı için tek noktada tut.
VAT_PERCENT = 20

# Archive add-on (tek seçenek, sabit fiyat).
ARCHIVE_ADDON_GB = 100
ARCHIVE_ADDON_PRICE_TRY = 10000  # yıllık, KDV hariç


def validate_seat_count(plan: str, seat_count: int) -> bool:
    """Return True if seat_count is within the allowed range for the plan."""
    definition = PLAN_CATALOG.get(plan)
    if definition is None:
        return False
    if seat_count < definition["min_users"]:
        return False
    if definition["max_users"] is not None and seat_count > definition["max_users"]:
        return False
    return True


def calculate_plan_total_try(plan: str, seat_count: int) -> int:
    """Total TRY (yearly, VAT-exclusive) for given plan × seats. Raises KeyError
    on unknown plan — caller should validate first."""
    definition = PLAN_CATALOG[plan]
    return int(definition["price_try_per_user_yearly"]) * int(seat_count)

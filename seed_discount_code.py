"""
Discount code seed/manage script.

Tek seferlik kampanya kodlarını DB'ye yazar. Idempotent — aynı kod zaten
varsa varsayılan olarak dokunmaz; `--update` flag'i ile alanlarını overlap'leyebilir.

Örnekler:

  # Default seed (HOSGELDIN10 → %10, süresiz, limitsiz)
  python seed_discount_code.py

  # Özel kod
  python seed_discount_code.py --code CENG10 --percent 10

  # Limitli, son kullanım tarihli
  python seed_discount_code.py --code KIS25 --percent 25 \\
      --max-uses 100 --valid-until 2027-01-01

  # Var olan kodu güncelle (örn. devre dışı bırak)
  python seed_discount_code.py --code HOSGELDIN10 --inactive --update

  # Listele
  python seed_discount_code.py --list

DB connection auth servisinin Settings.DATABASE_URL'inden alınır
(localhost:5441 / docker postgres / preprod env'den).
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from typing import Optional

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.discount_code import DiscountCode


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Discount code seed/manage")
    p.add_argument("--code", default="HOSGELDIN10", help="Indirim kodu (case-insensitive; upper-case'e cevrilir)")
    p.add_argument("--percent", type=int, default=10, help="Indirim yuzdesi (1-100)")
    p.add_argument("--max-uses", type=int, default=None, help="Toplam kullanim limiti (yoksa sinirsiz)")
    p.add_argument(
        "--valid-until",
        type=str,
        default=None,
        help="Son gecerlilik tarihi (YYYY-MM-DD veya YYYY-MM-DD HH:MM); yoksa suresiz",
    )
    p.add_argument("--inactive", action="store_true", help="Kodu pasif olarak ekle/guncelle")
    p.add_argument("--update", action="store_true", help="Var olan kodun alanlarini override et")
    p.add_argument("--list", action="store_true", help="Sadece mevcut kodlari listele")
    return p.parse_args(argv)


def parse_valid_until(value: Optional[str]) -> Optional[datetime]:
    if value is None or value == "":
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise SystemExit(f"--valid-until '{value}' formati gecersiz. Beklenen: YYYY-MM-DD veya YYYY-MM-DD HH:MM")


async def cmd_list() -> None:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(DiscountCode).order_by(DiscountCode.created_at.desc()))).scalars().all()
        if not rows:
            print("(no codes)")
            return
        for r in rows:
            tag = "active" if r.is_active else "INACTIVE"
            cap = f"{r.times_used}/{r.max_uses}" if r.max_uses is not None else f"{r.times_used}/∞"
            expiry = r.valid_until.strftime("%Y-%m-%d %H:%M") if r.valid_until else "süresiz"
            print(f"  [{tag:8s}] {r.code:20s}  %{r.percent_off:<3d}  uses={cap:8s}  expires={expiry}")


async def cmd_upsert(args: argparse.Namespace) -> None:
    code = args.code.strip().upper()
    if not code:
        raise SystemExit("--code bos olamaz")
    if not (1 <= args.percent <= 100):
        raise SystemExit("--percent 1 ile 100 arasinda olmali")

    valid_until = parse_valid_until(args.valid_until)

    async with AsyncSessionLocal() as db:
        existing = (await db.execute(select(DiscountCode).where(DiscountCode.code == code))).scalar_one_or_none()
        if existing is not None and not args.update:
            print(f"⚠️  '{code}' zaten var ({existing.percent_off}% off, "
                  f"{'active' if existing.is_active else 'inactive'}). Degistirmek icin --update kullan.")
            return

        if existing is None:
            row = DiscountCode(
                code=code,
                percent_off=args.percent,
                is_active=not args.inactive,
                valid_until=valid_until,
                max_uses=args.max_uses,
            )
            db.add(row)
            await db.commit()
            print(f"✅ Olusturuldu: {code} (%{args.percent} off, "
                  f"{'aktif' if not args.inactive else 'PASIF'}, "
                  f"max_uses={args.max_uses or '∞'}, expires={valid_until or 'süresiz'})")
            return

        existing.percent_off = args.percent
        existing.is_active = not args.inactive
        existing.valid_until = valid_until
        existing.max_uses = args.max_uses
        await db.commit()
        print(f"✅ Guncellendi: {code} (%{args.percent} off, "
              f"{'aktif' if not args.inactive else 'PASIF'}, "
              f"max_uses={args.max_uses or '∞'}, expires={valid_until or 'süresiz'})")


async def main(argv: list[str]) -> None:
    args = parse_args(argv)
    if args.list:
        await cmd_list()
        return
    await cmd_upsert(args)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))

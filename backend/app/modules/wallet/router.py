"""Digital Wallet: owned products and the risk alerts raised for them."""

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.deps import Db, Level1User
from app.models import Brand, Passport, Product, RiskEvent, UserRiskAlert, WalletItem
from app.modules.catalogue.service import find_product

router = APIRouter(tags=["wallet"])


class WalletItemIn(BaseModel):
    product_id: str
    add_method: Literal["scan", "search", "manual"] = "search"
    nickname: str | None = Field(None, max_length=80)


def _item(item: WalletItem, product: Product, brand: str | None,
          passport: Passport | None) -> dict[str, Any]:
    return {"id": str(item.id), "product_id": str(product.id), "slug": product.public_slug,
            "name": product.canonical_name, "brand": brand, "nickname": item.nickname,
            "alerts_enabled": item.alerts_enabled,
            "status_badge": passport.status_badge if passport else None,
            "trust_score": float(passport.trust_score)
            if passport and passport.trust_score is not None else None,
            "passport_changed": bool(passport and item.last_seen_passport_id != passport.id),
            "created_at": item.created_at.isoformat()}


@router.get("/wallet/items")
async def list_items(db: Db, user: Level1User) -> list[dict[str, Any]]:
    rows = (await db.execute(
        select(WalletItem, Product, Brand.name, Passport)
        .join(Product, Product.id == WalletItem.product_id)
        .outerjoin(Brand, Brand.id == Product.brand_id)
        .outerjoin(Passport, Passport.id == Product.current_passport_id)
        .where(WalletItem.user_id == user.id, WalletItem.deleted_at.is_(None))
        .order_by(WalletItem.created_at.desc()))).all()
    return [_item(*r) for r in rows]


@router.post("/wallet/items", status_code=status.HTTP_201_CREATED)
async def save_item(data: WalletItemIn, db: Db, user: Level1User) -> dict[str, Any]:
    product = await find_product(db, data.product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "product_not_found")
    if (await db.execute(select(WalletItem.id).where(
            WalletItem.user_id == user.id, WalletItem.product_id == product.id,
            WalletItem.deleted_at.is_(None)))).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "already_in_wallet")
    item = WalletItem(user_id=user.id, product_id=product.id, add_method=data.add_method,
                      nickname=data.nickname, last_seen_passport_id=product.current_passport_id)
    db.add(item)
    await db.flush()
    await db.refresh(item)
    passport = (await db.get(Passport, product.current_passport_id)
                if product.current_passport_id else None)
    brand = await db.scalar(select(Brand.name).where(Brand.id == product.brand_id))
    return _item(item, product, brand, passport)


@router.delete("/wallet/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_item(item_id: uuid.UUID, db: Db, user: Level1User) -> None:
    # Another user's item is a 404, never a 403: its existence is not this caller's business.
    item = (await db.execute(select(WalletItem).where(
        WalletItem.id == item_id, WalletItem.user_id == user.id,
        WalletItem.deleted_at.is_(None)))).scalar_one_or_none()
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "wallet_item_not_found")
    item.deleted_at = datetime.now(UTC)


@router.get("/alerts")
async def list_alerts(db: Db, user: Level1User) -> list[dict[str, Any]]:
    rows = (await db.execute(
        select(UserRiskAlert, RiskEvent, Product)
        .join(RiskEvent, RiskEvent.id == UserRiskAlert.risk_event_id)
        .join(Product, Product.id == RiskEvent.product_id)
        .where(UserRiskAlert.user_id == user.id)
        .order_by(UserRiskAlert.created_at.desc()).limit(50))).all()
    return [{"id": str(a.id), "status": a.status, "severity": e.severity,
             "event_type": e.event_type, "title": e.title, "summary": e.summary,
             "product_slug": p.public_slug, "created_at": a.created_at.isoformat()}
            for a, e, p in rows]

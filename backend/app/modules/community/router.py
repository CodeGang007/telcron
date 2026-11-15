"""Reviews, helpful votes and hazard flags. Every write is signed by a Level 1 TelcronID."""

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.core.deps import Db, Level1User
from app.core.events import audit, emit
from app.models import (
    CoinBalance,
    HazardDimension,
    HazardFlag,
    Review,
    ReviewTask,
    ReviewVote,
    User,
)
from app.modules.catalogue.service import find_product
from app.modules.rewards import service as rewards

router = APIRouter(tags=["community"])


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    title: str | None = Field(None, max_length=120)
    body: str = Field(min_length=20, max_length=5000)


class ReviewOut(BaseModel):
    id: str
    rating: int
    title: str | None
    body: str
    author: str | None
    origin: str
    helpful_count: int
    created_at: datetime


class FlagIn(BaseModel):
    dimension_code: str | None = None
    description: str = Field(min_length=20, max_length=2000)


class CreatedOut(BaseModel):
    id: str
    coins_pending: int


async def _product(db: Db, id_or_slug: str):
    product = await find_product(db, id_or_slug)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "product_not_found")
    return product


@router.get("/products/{id_or_slug}/reviews", response_model=list[ReviewOut])
async def list_reviews(id_or_slug: str, db: Db,
                       limit: int = Query(20, ge=1, le=50)) -> list[ReviewOut]:
    product = await _product(db, id_or_slug)
    rows = (await db.execute(
        select(Review, User.display_name).outerjoin(User, User.id == Review.author_user_id)
        .where(Review.product_id == product.id, Review.status == "published",
               Review.deleted_at.is_(None))
        .order_by(Review.helpful_count.desc(), Review.created_at.desc()).limit(limit))).all()
    return [ReviewOut(id=str(r.id), rating=r.rating, title=r.title, body=r.body, author=name,
                      origin=r.origin, helpful_count=r.helpful_count, created_at=r.created_at)
            for r, name in rows]


@router.post("/products/{id_or_slug}/reviews", response_model=CreatedOut,
             status_code=status.HTTP_201_CREATED)
async def post_review(id_or_slug: str, data: ReviewIn, db: Db, user: Level1User) -> CreatedOut:
    product = await _product(db, id_or_slug)
    if (await db.execute(select(Review.id).where(
            Review.product_id == product.id, Review.author_user_id == user.id,
            Review.deleted_at.is_(None)))).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "already_reviewed")
    is_first = not (await db.execute(select(Review.id).where(
        Review.product_id == product.id, Review.origin == "user").limit(1))).first()
    balance = await db.get(CoinBalance, user.id)
    level = await rewards.level_for(db, int(balance.lifetime_earned) if balance else 0)
    review = Review(product_id=product.id, origin="user", author_user_id=user.id,
                    rating=data.rating, title=data.title, body=data.body,
                    author_reward_level=level.level if level else None)
    db.add(review)
    await db.flush()
    pending = 0
    for rule in ("review", *(("first_review",) if is_first else ())):
        entry = await rewards.earn(db, user.id, rule, subject_type="product",
                                   subject_id=product.id,
                                   idempotency_key=f"{rule}:{user.id}:{product.id}")
        pending += int(entry.amount) if entry else 0
    emit(db, "review", review.id, "ReviewSubmitted", {"product_id": str(product.id)})
    audit(db, action="review.create", entity_type="review", entity_id=review.id,
          actor_user_id=user.id)
    return CreatedOut(id=str(review.id), coins_pending=pending)


@router.post("/reviews/{review_id}/helpful", status_code=status.HTTP_204_NO_CONTENT)
async def vote_helpful(review_id: uuid.UUID, db: Db, user: Level1User) -> None:
    review = (await db.execute(select(Review).where(Review.id == review_id).with_for_update())
              ).scalar_one_or_none()
    if review is None or review.status != "published":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "review_not_found")
    if review.author_user_id == user.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "own_review")
    await db.execute(insert(ReviewVote).values(review_id=review_id, user_id=user.id)
                     .on_conflict_do_nothing())
    review.helpful_count = await db.scalar(
        select(func.count()).select_from(ReviewVote).where(ReviewVote.review_id == review_id))


@router.post("/products/{id_or_slug}/flags", response_model=CreatedOut,
             status_code=status.HTTP_201_CREATED)
async def flag_hazard(id_or_slug: str, data: FlagIn, db: Db, user: Level1User) -> CreatedOut:
    """Opens a flag and a safety-team task. Coins follow once a reviewer confirms it (WO-006)."""
    product = await _product(db, id_or_slug)
    if data.dimension_code and await db.get(HazardDimension, data.dimension_code) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "unknown_dimension")
    flag = HazardFlag(reporter_user_id=user.id, product_id=product.id,
                      dimension_code=data.dimension_code, description=data.description)
    db.add(flag)
    await db.flush()
    db.add(ReviewTask(task_type="hazard_flag", subject_type="hazard_flag", subject_id=flag.id,
                      priority=1, submitted_by_user_id=user.id,
                      payload={"product_id": str(product.id)}))
    audit(db, action="hazard_flag.create", entity_type="hazard_flag", entity_id=flag.id,
          actor_user_id=user.id)
    return CreatedOut(id=str(flag.id), coins_pending=0)

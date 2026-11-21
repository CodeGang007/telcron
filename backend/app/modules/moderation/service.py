"""The safety team's queue: every hazard flag, fact correction, fraud hold and thin assessment that
needs a person. Resolving a task is what makes a contribution count: the coins, the member's
trust score, the re-screen and the alert all follow from the decision made here."""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import audit, emit
from app.domain import trust
from app.models import (
    FraudHold,
    HazardFlag,
    Product,
    ProductFactReport,
    ReviewTask,
    RiskEvent,
    TrustScoreEvent,
    User,
)
from app.modules.rewards import service as rewards

OPEN = ("open", "in_progress")
# Corrections to these change the product row itself; anything else lands in `specifications`.
PRODUCT_FIELDS = ("canonical_name", "model_number", "description")
RESOLVE_HOLD = text(
    "select coin_resolve_hold(cast(:hold as uuid), :is_fraud, cast(:actor as uuid))")


def _now() -> datetime:
    return datetime.now(UTC)


async def _adjust_trust(db: AsyncSession, user_id: uuid.UUID, reason: str,
                        reference_type: str, reference_id: uuid.UUID) -> None:
    user = (await db.execute(select(User).where(User.id == user_id).with_for_update())).scalar_one()
    after, change = trust.apply(user.trust_score, reason)
    if change == 0:
        return
    user.trust_score = after
    db.add(TrustScoreEvent(user_id=user_id, delta=change, score_after=after, reason_code=reason,
                           reference_type=reference_type, reference_id=reference_id))


async def _product_summary(db: AsyncSession, product_id: uuid.UUID) -> dict[str, Any]:
    row = (await db.execute(select(Product.public_slug, Product.canonical_name)
                            .where(Product.id == product_id))).one()
    return {"slug": row.public_slug, "name": row.canonical_name}


async def describe(db: AsyncSession, task: ReviewTask) -> dict[str, Any]:
    """A task with enough of its subject for a reviewer to decide without leaving the queue."""
    subject: dict[str, Any] = {}
    if task.task_type == "hazard_flag":
        flag = await db.get(HazardFlag, task.subject_id)
        reporter = await db.get(User, flag.reporter_user_id)
        subject = {"description": flag.description, "dimension_code": flag.dimension_code,
                   "status": flag.status, "reporter": reporter.display_name,
                   "reporter_trust": float(reporter.trust_score),
                   "product": await _product_summary(db, flag.product_id)}
    elif task.task_type == "fact_report":
        report = await db.get(ProductFactReport, task.subject_id)
        reporter = await db.get(User, report.reporter_user_id)
        subject = {"attribute": report.attribute, "current_value": report.current_value,
                   "proposed_value": report.proposed_value,
                   "is_confirmation": report.is_confirmation, "status": report.status,
                   "reporter": reporter.display_name,
                   "product": await _product_summary(db, report.product_id)}
    elif task.task_type == "fraud_hold":
        hold = await db.get(FraudHold, task.subject_id)
        member = await db.get(User, hold.user_id)
        subject = {"reason": hold.reason, "rule_triggered": hold.rule_triggered,
                   "status": hold.status, "member": member.display_name}
    elif task.payload.get("product_id"):
        subject = {"product": await _product_summary(db, uuid.UUID(task.payload["product_id"]))}
    return {"id": str(task.id), "task_type": task.task_type, "status": task.status,
            "priority": task.priority, "created_at": task.created_at.isoformat(),
            "resolution": task.resolution, "subject": subject}


async def list_tasks(db: AsyncSession, limit: int) -> list[dict[str, Any]]:
    tasks = (await db.execute(select(ReviewTask).where(ReviewTask.status.in_(OPEN))
                              .order_by(ReviewTask.priority, ReviewTask.created_at)
                              .limit(limit))).scalars().all()
    return [await describe(db, t) for t in tasks]


# The member a task's subject belongs to: the reporter of a flag or correction, the holder of a
# frozen balance. Any other task type falls back to whoever submitted the task (S-20), so a type
# added later is covered without anyone remembering to list it here.
SUBJECT_OWNER = {
    "hazard_flag": (HazardFlag, HazardFlag.reporter_user_id),
    "fact_report": (ProductFactReport, ProductFactReport.reporter_user_id),
    "fraud_hold": (FraudHold, FraudHold.user_id),
}


async def _subject_owner(db: AsyncSession, task: ReviewTask) -> uuid.UUID | None:
    if task.task_type not in SUBJECT_OWNER:
        return task.submitted_by_user_id
    model, owner = SUBJECT_OWNER[task.task_type]
    return await db.scalar(select(owner).where(model.id == task.subject_id))


async def _locked_task(db: AsyncSession, task_id: uuid.UUID, staff: User) -> ReviewTask:
    """The open task, locked, provided the reviewer has no stake in it. Nobody decides a task about
    their own contribution or their own coins (DEF-011): 403, not 404, because the task is in the
    queue the reviewer has just read; hiding it would not hide anything."""
    task = (await db.execute(select(ReviewTask).where(ReviewTask.id == task_id).with_for_update())
            ).scalar_one_or_none()
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "review_task_not_found")
    if task.status not in OPEN:
        raise HTTPException(status.HTTP_409_CONFLICT, "review_task_closed")
    if await _subject_owner(db, task) == staff.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "own_item")
    return task


async def claim(db: AsyncSession, task_id: uuid.UUID, staff: User) -> ReviewTask:
    task = await _locked_task(db, task_id, staff)
    task.status, task.assigned_to_user_id = "in_progress", staff.id
    return task


async def _resolve_flag(db: AsyncSession, task: ReviewTask, staff: User, decision: str,
                        note: str | None) -> None:
    flag = (await db.execute(select(HazardFlag).where(HazardFlag.id == task.subject_id)
                             .with_for_update())).scalar_one()
    if flag.status != "pending":
        if decision == "dismiss":
            return
        raise HTTPException(status.HTTP_409_CONFLICT, "already_decided")
    confirm = decision == "confirm"
    flag.status = "confirmed" if confirm else "rejected"
    if decision == "dismiss":
        note = note or "Closed by the safety team without a finding."
    flag.reviewed_by_user_id, flag.reviewed_at, flag.resolution_note = staff.id, _now(), note
    await db.flush()
    if decision == "dismiss":
        # Closed without a finding: the flag stops being pending (so its reporter may flag the
        # product again), pays nothing and costs no trust. `flag_status` has no `dismissed`.
        return
    await _adjust_trust(db, flag.reporter_user_id,
                        "hazard_flag_confirmed" if confirm else "hazard_flag_rejected",
                        "hazard_flag", flag.id)
    if not confirm:
        return
    await rewards.earn(db, flag.reporter_user_id, "hazard_flag_confirmed",
                       subject_type="product", subject_id=flag.product_id,
                       idempotency_key=f"hazard_flag_confirmed:{flag.id}")
    product = await db.get(Product, flag.product_id)
    event = RiskEvent(product_id=product.id, event_type="community_flag_confirmed",
                      severity="medium", hazard_flag_id=flag.id,
                      title=f"{product.canonical_name}: a hazard report was confirmed"[:200],
                      summary=(flag.description or "")[:300] or None)
    db.add(event)
    await db.flush()
    # Everyone holding the product hears about it, and the flag becomes evidence for a re-screen.
    emit(db, "risk_event", event.id, "RiskEventRaised",
         {"product_id": str(product.id), "risk_event_id": str(event.id),
          "passport_id": str(product.current_passport_id) if product.current_passport_id else None})
    emit(db, "hazard_flag", flag.id, "HazardFlagConfirmed", {"product_id": str(product.id)})


async def _resolve_fact(db: AsyncSession, task: ReviewTask, staff: User, decision: str) -> None:
    report = (await db.execute(select(ProductFactReport).where(
        ProductFactReport.id == task.subject_id).with_for_update())).scalar_one()
    if report.status != "pending":
        if decision == "dismiss":
            return
        raise HTTPException(status.HTTP_409_CONFLICT, "already_decided")
    accept = decision == "confirm"
    report.status = "accepted" if accept else "rejected"
    report.reviewed_by_user_id, report.reviewed_at = staff.id, _now()
    await db.flush()
    if decision == "dismiss":
        return  # closed without a finding: rejected, no trust penalty, no coins
    await _adjust_trust(db, report.reporter_user_id,
                        "fact_report_accepted" if accept else "fact_report_rejected",
                        "product_fact_report", report.id)
    if not accept:
        return
    product = (await db.execute(select(Product).where(Product.id == report.product_id)
                                .with_for_update())).scalar_one()
    if not report.is_confirmation:
        if report.attribute in PRODUCT_FIELDS:
            before = getattr(product, report.attribute)
            setattr(product, report.attribute, report.proposed_value)
            if report.attribute == "model_number":
                product.model_number_normalized = "".join(
                    ch for ch in report.proposed_value.upper() if ch.isalnum()) or None
        else:
            before = product.specifications.get(report.attribute)
            product.specifications = {**product.specifications,
                                      report.attribute: report.proposed_value}
        try:
            await db.flush()
        except IntegrityError as exc:  # e.g. another product of the brand already has that model
            raise HTTPException(status.HTTP_409_CONFLICT, "correction_conflicts") from exc
        audit(db, action="product.corrected", entity_type="product", entity_id=product.id,
              actor_user_id=staff.id, actor_type="admin",
              changes={report.attribute: [before, report.proposed_value]})
        emit(db, "product", product.id, "ProductCorrected", {"product_id": str(product.id)})
    await rewards.earn(db, report.reporter_user_id, "fact_verification", subject_type="product",
                       subject_id=product.id, idempotency_key=f"fact_verification:{report.id}")


async def _resolve_hold(db: AsyncSession, task: ReviewTask, staff: User, decision: str) -> None:
    hold = (await db.execute(select(FraudHold).where(FraudHold.id == task.subject_id)
                             .with_for_update())).scalar_one()
    if hold.status != "open":
        if decision == "dismiss":
            return
        raise HTTPException(status.HTTP_409_CONFLICT, "already_decided")
    await db.execute(RESOLVE_HOLD, {"hold": hold.id, "is_fraud": decision == "confirm",
                                    "actor": staff.id})
    await db.refresh(hold)  # the function changed the row behind the session


async def resolve(db: AsyncSession, task_id: uuid.UUID, staff: User, decision: str,
                  note: str | None) -> ReviewTask:
    """`confirm` upholds the subject (a real hazard, a correct fact, real fraud); `reject` does the
    opposite; `dismiss` closes the task without a finding. Without a finding nothing stays open
    (DEF-012): a flag or correction is rejected with no trust penalty, and a fraud hold is released,
    because only a finding of fraud forfeits coins."""
    task = await _locked_task(db, task_id, staff)
    if task.task_type == "hazard_flag":
        await _resolve_flag(db, task, staff, decision, note)
    elif task.task_type == "fact_report":
        await _resolve_fact(db, task, staff, decision)
    elif task.task_type == "fraud_hold":
        await _resolve_hold(db, task, staff, decision)
    task.status = "dismissed" if decision == "dismiss" else "resolved"
    task.resolution = f"{decision}: {note}" if note else decision
    task.resolved_at = _now()
    task.assigned_to_user_id = task.assigned_to_user_id or staff.id
    audit(db, action=f"review_task.{decision}", entity_type="review_task", entity_id=task.id,
          actor_user_id=staff.id, actor_type="admin",
          changes={"task_type": task.task_type, "subject_id": str(task.subject_id)})
    return task

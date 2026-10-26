from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.auth.dependencies import get_current_user, require_operational
from app.database import get_db
from app.models import InventoryBalance, Item, Location, StockMovement, Transfer, User
from app.schemas import TransferIn, TransferOut, TransferStatusIn
from app.services.activity import log_activity

router = APIRouter(prefix="/transfers", tags=["Transfers"])


def transfer_out(t: Transfer) -> TransferOut:
    return TransferOut(
        id=t.id,
        code=t.code,
        item_id=t.item_id,
        item_name=t.item.name,
        source_location_id=t.source_location_id,
        source_location_name=t.source_location.name,
        destination_location_id=t.destination_location_id,
        destination_location_name=t.destination_location.name,
        quantity=t.quantity,
        status=t.status,
        priority=t.priority,
        notes=t.notes,
        creator_name=t.creator.name,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


def load_transfer(db: Session, transfer_id: int) -> Transfer:
    transfer = db.scalar(
        select(Transfer)
        .where(Transfer.id == transfer_id)
        .options(
            joinedload(Transfer.item),
            joinedload(Transfer.source_location),
            joinedload(Transfer.destination_location),
            joinedload(Transfer.creator),
        )
    )
    if not transfer:
        raise HTTPException(404, "Transfer not found")
    return transfer


@router.get("", response_model=list[TransferOut])
def transfer_list(
    status: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = (
        select(Transfer)
        .options(
            joinedload(Transfer.item),
            joinedload(Transfer.source_location),
            joinedload(Transfer.destination_location),
            joinedload(Transfer.creator),
        )
        .order_by(Transfer.created_at.desc())
    )
    if status and status != "all":
        query = query.where(Transfer.status == status)

    return [transfer_out(t) for t in db.scalars(query).unique()]


@router.get("/{transfer_id}", response_model=TransferOut)
def transfer_get(
    transfer_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return transfer_out(load_transfer(db, transfer_id))


@router.post("", response_model=TransferOut, status_code=201)
def transfer_create(
    data: TransferIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_operational),
):
    try:
        if db.bind.dialect.name == "sqlite":
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        item = db.get(Item, data.item_id)
        source = db.get(Location, data.source_location_id)
        destination = db.get(Location, data.destination_location_id)
        if not item:
            raise HTTPException(404, "Prece nav atrasta")
        if not source or not destination:
            raise HTTPException(404, "Noliktavas vieta nav atrasta")

        balance = db.scalar(
            select(InventoryBalance)
            .where(
                InventoryBalance.item_id == data.item_id,
                InventoryBalance.location_id == data.source_location_id,
            )
            .with_for_update()
        )
        total_reserved = db.scalar(
            select(func.coalesce(func.sum(Transfer.quantity), 0)).where(
                Transfer.item_id == data.item_id,
                Transfer.source_location_id == data.source_location_id,
                Transfer.status.in_(["pending", "in-transit"]),
            )
        ) or 0
        available = (balance.quantity if balance else 0) - int(total_reserved)
        if data.quantity > available:
            raise HTTPException(422, f"Nepietiekams pieejamais krājums (pieejams: {max(0, available)})")

        used_at_destination = db.scalar(
            select(func.coalesce(func.sum(InventoryBalance.quantity), 0)).where(
                InventoryBalance.location_id == data.destination_location_id
            )
        ) or 0
        if used_at_destination + data.quantity > destination.capacity:
            raise HTTPException(422, "Galamērķa vietā nepietiek ietilpības")

        transfer = Transfer(**data.model_dump(), code="PAGAIDU", creator_id=user.id)
        db.add(transfer)
        db.flush()
        transfer.code = f"PRV-{transfer.id:05d}"
        log_activity(
            db,
            user,
            "create",
            "transfer",
            transfer.id,
            f"Created transfer {transfer.code}",
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(500, "Failed to create transfer")

    return transfer_out(load_transfer(db, transfer.id))


@router.patch("/{transfer_id}", response_model=TransferOut)
def transfer_status(
    transfer_id: int,
    data: TransferStatusIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_operational),
):
    try:
        if db.bind.dialect.name == "sqlite":
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        transfer = db.scalar(
            select(Transfer)
            .where(Transfer.id == transfer_id)
            .with_for_update()
        )
        if not transfer:
            raise HTTPException(404, "Pārvietojums nav atrasts")
        allowed = {
            "pending": {"in-transit", "cancelled"},
            "in-transit": {"done", "cancelled"},
            "done": set(),
            "cancelled": set(),
        }
        if data.status not in allowed.get(transfer.status, set()):
            raise HTTPException(422, "Šāda statusa maiņa nav atļauta")

        if data.status == "done":
            source_balance = db.scalar(
                select(InventoryBalance)
                .where(
                    InventoryBalance.item_id == transfer.item_id,
                    InventoryBalance.location_id == transfer.source_location_id,
                )
                .with_for_update()
            )
            if not source_balance or source_balance.quantity < transfer.quantity:
                raise HTTPException(422, "Avota vietā vairs nav pietiekama krājuma")
            destination = db.get(Location, transfer.destination_location_id)
            destination_used = db.scalar(
                select(func.coalesce(func.sum(InventoryBalance.quantity), 0)).where(
                    InventoryBalance.location_id == transfer.destination_location_id
                )
            ) or 0
            if destination_used + transfer.quantity > destination.capacity:
                raise HTTPException(422, "Galamērķa vietā nepietiek ietilpības")
            destination_balance = db.scalar(
                select(InventoryBalance)
                .where(
                    InventoryBalance.item_id == transfer.item_id,
                    InventoryBalance.location_id == transfer.destination_location_id,
                )
                .with_for_update()
            )
            source_balance.quantity -= transfer.quantity
            if destination_balance:
                destination_balance.quantity += transfer.quantity
            else:
                db.add(InventoryBalance(
                    item_id=transfer.item_id,
                    location_id=transfer.destination_location_id,
                    quantity=transfer.quantity,
                ))
            db.add(StockMovement(
                item_id=transfer.item_id,
                transfer_id=transfer.id,
                source_location_id=transfer.source_location_id,
                destination_location_id=transfer.destination_location_id,
                quantity=transfer.quantity,
                action="transfer_completed",
                user_id=user.id,
            ))

        transfer.status = data.status
        transfer.updated_at = datetime.now(timezone.utc)
        log_activity(
            db,
            user,
            "status",
            "transfer",
            transfer.id,
            f"Pārvietojuma {transfer.code} statuss mainīts uz {data.status}",
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(500, "Failed to update transfer status")

    return transfer_out(load_transfer(db, transfer_id))


@router.delete("/{transfer_id}", status_code=204)
def transfer_delete(
    transfer_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_operational),
):
    transfer = load_transfer(db, transfer_id)

    if transfer.status not in {"pending", "cancelled"}:
        raise HTTPException(
            409,
            "Only pending or cancelled transfers can be deleted",
        )

    code = transfer.code

    try:
        db.delete(transfer)
        log_activity(
            db,
            user,
            "delete",
            "transfer",
            transfer_id,
            f"Deleted transfer {code}",
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(500, "Failed to delete transfer")

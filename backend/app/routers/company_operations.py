from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, joinedload

from app.auth.company_access import (
    CompanyAccessContext,
    require_company_edit_access,
    require_company_read_access,
)
from app.database import get_db
from app.models import ActivityLog, Category, InventoryBalance, Item, Location, Transfer
from app.schemas import TransferIn, TransferOut, TransferStatusIn
from app.services.activity import log_activity

router = APIRouter()


def _transfer_query(company_id: int):
    return select(Transfer).where(
        Transfer.company_id == company_id,
        Transfer.item.has(Item.company_id == company_id),
        Transfer.source_location.has(Location.company_id == company_id),
        Transfer.destination_location.has(Location.company_id == company_id),
    ).options(
        joinedload(Transfer.item), joinedload(Transfer.source_location),
        joinedload(Transfer.destination_location), joinedload(Transfer.creator),
    )


def _load_transfer(db: Session, company_id: int, transfer_id: int) -> Transfer:
    transfer = db.scalar(_transfer_query(company_id).where(Transfer.id == transfer_id))
    if transfer is None:
        raise HTTPException(404, "Transfer not found")
    return transfer


def _transfer_out(transfer: Transfer) -> TransferOut:
    return TransferOut(
        id=transfer.id, code=transfer.code, item_id=transfer.item_id,
        item_name=transfer.item.name, source_location_id=transfer.source_location_id,
        source_location_name=transfer.source_location.name,
        destination_location_id=transfer.destination_location_id,
        destination_location_name=transfer.destination_location.name,
        quantity=transfer.quantity, status=transfer.status, priority=transfer.priority,
        notes=transfer.notes, creator_name=transfer.creator.name,
        created_at=transfer.created_at, updated_at=transfer.updated_at,
    )


def _company_resource(db: Session, model, company_id: int, resource_id: int, label: str):
    resource = db.scalar(select(model).where(
        model.company_id == company_id, model.id == resource_id
    ))
    if resource is None:
        raise HTTPException(404, f"{label} not found")
    return resource


@router.get("/transfers", response_model=list[TransferOut])
def transfer_list(
    company_id: int, status: str | None = None, db: Session = Depends(get_db),
    _: CompanyAccessContext = Depends(require_company_read_access),
):
    query = _transfer_query(company_id).order_by(Transfer.created_at.desc())
    if status and status != "all":
        query = query.where(Transfer.status == status)
    return [_transfer_out(row) for row in db.scalars(query).unique()]


@router.get("/transfers/{transfer_id}", response_model=TransferOut)
def transfer_get(
    company_id: int, transfer_id: int, db: Session = Depends(get_db),
    _: CompanyAccessContext = Depends(require_company_read_access),
):
    return _transfer_out(_load_transfer(db, company_id, transfer_id))


@router.post("/transfers", response_model=TransferOut, status_code=201)
def transfer_create(
    company_id: int, data: TransferIn, db: Session = Depends(get_db),
    access: CompanyAccessContext = Depends(require_company_edit_access),
):
    item = _company_resource(db, Item, company_id, data.item_id, "Item")
    _company_resource(db, Location, company_id, data.source_location_id, "Source location")
    _company_resource(
        db, Location, company_id, data.destination_location_id, "Destination location"
    )
    balance = db.scalar(select(InventoryBalance).where(
        InventoryBalance.company_id == company_id,
        InventoryBalance.item_id == item.id,
        InventoryBalance.location_id == data.source_location_id,
    ))
    if balance is None:
        raise HTTPException(
            409, "Per-location inventory is not initialized for this item and source"
        )
    ledger_total = db.scalar(select(func.coalesce(func.sum(InventoryBalance.quantity), 0)).where(
        InventoryBalance.company_id == company_id,
        InventoryBalance.item_id == item.id,
    ))
    if ledger_total != item.stock:
        raise HTTPException(409, "Per-location inventory does not match item total stock")
    reservation = db.execute(
        update(InventoryBalance).where(
            InventoryBalance.id == balance.id,
            InventoryBalance.quantity - InventoryBalance.reserved >= data.quantity,
        ).values(
            reserved=InventoryBalance.reserved + data.quantity,
            updated_at=datetime.now(timezone.utc),
        )
    )
    if reservation.rowcount != 1:
        db.rollback()
        raise HTTPException(422, "Insufficient available stock")
    transfer = Transfer(
        company_id=company_id, **data.model_dump(), code="PENDING",
        creator_id=access.user.id,
    )
    db.add(transfer)
    db.flush()
    transfer.code = f"PRV-{transfer.id:05d}"
    log_activity(
        db, access.user, "create", "transfer", transfer.id,
        f"Created transfer {transfer.code}", company_id=company_id,
    )
    db.commit()
    return _transfer_out(_load_transfer(db, company_id, transfer.id))


def _release_reservation(db: Session, transfer: Transfer) -> None:
    released = db.execute(
        update(InventoryBalance).where(
            InventoryBalance.company_id == transfer.company_id,
            InventoryBalance.item_id == transfer.item_id,
            InventoryBalance.location_id == transfer.source_location_id,
            InventoryBalance.reserved >= transfer.quantity,
        ).values(
            reserved=InventoryBalance.reserved - transfer.quantity,
            updated_at=datetime.now(timezone.utc),
        )
    )
    if released.rowcount != 1:
        raise HTTPException(409, "Inventory reservation is inconsistent")


def _complete_transfer(db: Session, transfer: Transfer) -> None:
    moved = db.execute(
        update(InventoryBalance).where(
            InventoryBalance.company_id == transfer.company_id,
            InventoryBalance.item_id == transfer.item_id,
            InventoryBalance.location_id == transfer.source_location_id,
            InventoryBalance.quantity >= transfer.quantity,
            InventoryBalance.reserved >= transfer.quantity,
        ).values(
            quantity=InventoryBalance.quantity - transfer.quantity,
            reserved=InventoryBalance.reserved - transfer.quantity,
            updated_at=datetime.now(timezone.utc),
        )
    )
    if moved.rowcount != 1:
        raise HTTPException(409, "Reserved inventory cannot be completed")
    destination = db.scalar(select(InventoryBalance).where(
        InventoryBalance.company_id == transfer.company_id,
        InventoryBalance.item_id == transfer.item_id,
        InventoryBalance.location_id == transfer.destination_location_id,
    ))
    if destination is None:
        db.add(InventoryBalance(
            company_id=transfer.company_id, item_id=transfer.item_id,
            location_id=transfer.destination_location_id,
            quantity=transfer.quantity, reserved=0,
        ))
    else:
        destination.quantity += transfer.quantity
        destination.updated_at = datetime.now(timezone.utc)
    db.flush()
    positive_locations = list(db.scalars(select(InventoryBalance.location_id).where(
        InventoryBalance.company_id == transfer.company_id,
        InventoryBalance.item_id == transfer.item_id,
        InventoryBalance.quantity > 0,
    )))
    if len(positive_locations) == 1:
        transfer.item.location_id = positive_locations[0]


@router.patch("/transfers/{transfer_id}", response_model=TransferOut)
def transfer_status(
    company_id: int, transfer_id: int, data: TransferStatusIn,
    db: Session = Depends(get_db),
    access: CompanyAccessContext = Depends(require_company_edit_access),
):
    transfer = _load_transfer(db, company_id, transfer_id)
    allowed = {
        "pending": {"in-transit", "cancelled"},
        "in-transit": {"done", "cancelled"},
        "done": set(),
        "cancelled": set(),
    }
    if data.status not in allowed.get(transfer.status, set()):
        raise HTTPException(422, "Transfer status transition is not allowed")
    if data.status == "cancelled":
        _release_reservation(db, transfer)
    elif data.status == "done":
        _complete_transfer(db, transfer)
    transfer.status = data.status
    transfer.updated_at = datetime.now(timezone.utc)
    log_activity(
        db, access.user, "status", "transfer", transfer.id,
        f"Transfer {transfer.code} status changed to {data.status}",
        company_id=company_id,
    )
    db.commit()
    return _transfer_out(_load_transfer(db, company_id, transfer.id))


@router.delete("/transfers/{transfer_id}", status_code=204)
def transfer_delete(
    company_id: int, transfer_id: int, db: Session = Depends(get_db),
    access: CompanyAccessContext = Depends(require_company_edit_access),
):
    transfer = _load_transfer(db, company_id, transfer_id)
    if transfer.status not in {"pending", "cancelled"}:
        raise HTTPException(409, "Only pending or cancelled transfers can be deleted")
    if transfer.status == "pending":
        _release_reservation(db, transfer)
    code = transfer.code
    db.delete(transfer)
    log_activity(
        db, access.user, "delete", "transfer", transfer_id,
        f"Deleted transfer {code}", company_id=company_id,
    )
    db.commit()
    return Response(status_code=204)


@router.get("/dashboard")
def dashboard(
    company_id: int, db: Session = Depends(get_db),
    _: CompanyAccessContext = Depends(require_company_read_access),
):
    items = list(db.scalars(select(Item).where(Item.company_id == company_id)))
    transfers = list(db.scalars(_transfer_query(company_id)).unique())
    activities = list(db.scalars(
        select(ActivityLog).where(ActivityLog.company_id == company_id)
        .options(joinedload(ActivityLog.user))
        .order_by(ActivityLog.created_at.desc()).limit(8)
    ))
    return {
        "totalItems": len(items),
        "totalUnits": sum(item.stock for item in items),
        "lowStockCount": sum(
            item.stock < item.min_stock and item.stock > item.min_stock * .3
            for item in items
        ),
        "criticalStockCount": sum(
            item.stock <= item.min_stock * .3 for item in items
        ),
        "activeTransfers": sum(
            transfer.status in {"pending", "in-transit"} for transfer in transfers
        ),
        "stockValue": round(sum(item.stock * item.price for item in items), 2),
        "activities": [
            {"id": activity.id, "message": activity.message,
             "userName": activity.user.name if activity.user else None,
             "createdAt": activity.created_at.isoformat()}
            for activity in activities
        ],
    }


@router.get("/reports")
def reports(
    company_id: int, db: Session = Depends(get_db),
    _: CompanyAccessContext = Depends(require_company_read_access),
):
    items = list(db.scalars(
        select(Item).where(
            Item.company_id == company_id,
            Item.category.has(Category.company_id == company_id),
        ).options(joinedload(Item.category))
    ))
    completed = list(db.scalars(
        select(Transfer).where(
            Transfer.company_id == company_id, Transfer.status == "done",
            Transfer.item.has(Item.company_id == company_id),
            Transfer.source_location.has(Location.company_id == company_id),
            Transfer.destination_location.has(Location.company_id == company_id),
        ).options(joinedload(Transfer.item))
    ).unique())
    categories = {}
    for item in items:
        entry = categories.setdefault(
            item.category_id, {"name": item.category.name, "units": 0}
        )
        entry["units"] += item.stock
    movement = {}
    for transfer in completed:
        entry = movement.setdefault(
            transfer.item_id, {"name": transfer.item.name, "movement": 0}
        )
        entry["movement"] += transfer.quantity
    return {
        "totalUnits": sum(item.stock for item in items),
        "totalValue": round(sum(item.stock * item.price for item in items), 2),
        "completedTransfers": len(completed),
        "lowStockCount": sum(item.stock < item.min_stock for item in items),
        "categoryDistribution": list(categories.values()),
        "topItems": sorted(
            movement.values(), key=lambda entry: entry["movement"], reverse=True
        )[:5],
    }


@router.get("/activity")
def activity(
    company_id: int, db: Session = Depends(get_db),
    _: CompanyAccessContext = Depends(require_company_read_access),
):
    rows = db.scalars(
        select(ActivityLog).where(ActivityLog.company_id == company_id)
        .options(joinedload(ActivityLog.user))
        .order_by(ActivityLog.created_at.desc()).limit(50)
    )
    return [
        {"id": row.id, "message": row.message, "action": row.action,
         "entityType": row.entity_type,
         "userName": row.user.name if row.user else None,
         "createdAt": row.created_at.isoformat()}
        for row in rows
    ]

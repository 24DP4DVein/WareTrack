from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Item, Location, Transfer, User
from app.schemas import TransferIn, TransferOut, TransferStatusIn
from app.services.activity import log_activity

router = APIRouter(prefix="/transfers", tags=["P?ürvieto?Īana"])


def transfer_out(t: Transfer) -> TransferOut:
    return TransferOut(id=t.id, code=t.code, item_id=t.item_id, item_name=t.item.name,
        source_location_id=t.source_location_id, source_location_name=t.source_location.name,
        destination_location_id=t.destination_location_id, destination_location_name=t.destination_location.name,
        quantity=t.quantity, status=t.status, priority=t.priority, notes=t.notes,
        creator_name=t.creator.name, created_at=t.created_at, updated_at=t.updated_at)


def load_transfer(db: Session, transfer_id: int) -> Transfer:
    t = db.scalar(select(Transfer).where(Transfer.id == transfer_id).options(
        joinedload(Transfer.item), joinedload(Transfer.source_location),
        joinedload(Transfer.destination_location), joinedload(Transfer.creator)))
    if not t: raise HTTPException(404, "P?ürvietojums nav atrasts")
    return t


@router.get("", response_model=list[TransferOut])
def transfer_list(status: str | None = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    query = select(Transfer).options(joinedload(Transfer.item), joinedload(Transfer.source_location),
        joinedload(Transfer.destination_location), joinedload(Transfer.creator)).order_by(Transfer.created_at.desc())
    if status and status != "all": query = query.where(Transfer.status == status)
    return [transfer_out(t) for t in db.scalars(query).unique()]


@router.get("/{transfer_id}", response_model=TransferOut)
def transfer_get(transfer_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return transfer_out(load_transfer(db, transfer_id))


@router.post("", response_model=TransferOut, status_code=201)
def transfer_create(data: TransferIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.get(Item, data.item_id)
    if not item: raise HTTPException(422, "Prece nav atrasta")
    if not db.get(Location, data.source_location_id) or not db.get(Location, data.destination_location_id):
        raise HTTPException(422, "Noliktavas vieta nav atrasta")
    if item.location_id != data.source_location_id:
        raise HTTPException(422, "Prece neatrodas izv?ōl?ōtaj?ü s?ükuma viet?ü")
    reserved = sum(t.quantity for t in item.transfers if t.status in {"pending", "in-transit"})
    if data.quantity > item.stock - reserved:
        raise HTTPException(422, f"Nepietiekams pieejamais atlikums (pieejams: {max(0, item.stock - reserved)})")
    transfer = Transfer(**data.model_dump(), code="PAGAIDU", creator_id=user.id)
    db.add(transfer); db.flush(); transfer.code = f"PRV-{transfer.id:05d}"
    log_activity(db, user, "create", "transfer", transfer.id, f"Izveidots p?ürvietojums {transfer.code}")
    db.commit()
    return transfer_out(load_transfer(db, transfer.id))


@router.patch("/{transfer_id}", response_model=TransferOut)
def transfer_status(transfer_id: int, data: TransferStatusIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    transfer = load_transfer(db, transfer_id)
    allowed = {"pending": {"in-transit", "cancelled"}, "in-transit": {"done", "cancelled"},
               "done": set(), "cancelled": set()}
    if data.status not in allowed[transfer.status]:
        raise HTTPException(422, "?Ā?üda statusa mai?åa nav at??auta")
    transfer.status = data.status; transfer.updated_at = datetime.now(timezone.utc)
    if data.status == "done" and transfer.quantity == transfer.item.stock:
        transfer.item.location_id = transfer.destination_location_id
    log_activity(db, user, "status", "transfer", transfer.id,
                 f"P?ürvietojuma {transfer.code} statuss main?½ts uz ŌĆ£{data.status}ŌĆØ")
    db.commit()
    return transfer_out(load_transfer(db, transfer.id))


@router.delete("/{transfer_id}", status_code=204)
def transfer_delete(transfer_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    transfer = load_transfer(db, transfer_id)
    if transfer.status not in {"pending", "cancelled"}:
        raise HTTPException(409, "Var dz?ōst tikai gaido?Īu vai atceltu p?ürvietojumu")
    code = transfer.code; db.delete(transfer)
    log_activity(db, user, "delete", "transfer", transfer_id, f"Dz?ōsts p?ürvietojums {code}")
    db.commit()


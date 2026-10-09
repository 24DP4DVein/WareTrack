from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Category, Item, Location, Supplier, User
from app.schemas import ItemIn, ItemList, ItemOut, ItemUpdate
from app.services.activity import log_activity

router = APIRouter(prefix="/items", tags=["Preces"])


def item_out(item: Item) -> ItemOut:
    status = "critical" if item.stock <= item.min_stock * .3 else "low" if item.stock < item.min_stock else "ok"
    return ItemOut.model_validate({
        "id": item.id, "name": item.name, "sku": item.sku, "category_id": item.category_id,
        "supplier_id": item.supplier_id, "location_id": item.location_id, "stock": item.stock,
        "min_stock": item.min_stock, "price": item.price, "description": item.description,
        "category_name": item.category.name, "supplier_name": item.supplier.name if item.supplier else None,
        "location_name": item.location.name, "status": status, "created_at": item.created_at, "updated_at": item.updated_at,
    })


def validate_relations(db: Session, data: ItemIn):
    if not db.get(Category, data.category_id):
        raise HTTPException(422, "Nor?üd?½t?ü kategorija neeksist?ō")
    if not db.get(Location, data.location_id):
        raise HTTPException(422, "Nor?üd?½t?ü noliktavas vieta neeksist?ō")
    if data.supplier_id and not db.get(Supplier, data.supplier_id):
        raise HTTPException(422, "Nor?üd?½tais pieg?üd?üt?üjs neeksist?ō")


@router.get("", response_model=ItemList)
def list_items(search: str = "", category: int | None = None, status: str | None = None,
               page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100), db: Session = Depends(get_db)):
    query = select(Item).options(joinedload(Item.category), joinedload(Item.supplier), joinedload(Item.location))
    if search:
        q = f"%{search.strip()}%"
        query = query.where(or_(Item.name.ilike(q), Item.sku.ilike(q)))
    if category:
        query = query.where(Item.category_id == category)
    all_items = list(db.scalars(query.order_by(Item.created_at.desc())).unique())
    if status in {"ok", "low", "critical"}:
        all_items = [i for i in all_items if item_out(i).status == status]
    total = len(all_items)
    selected = all_items[(page - 1) * page_size: page * page_size]
    return ItemList(items=[item_out(i) for i in selected], total=total, page=page, page_size=page_size)


@router.get("/{item_id}", response_model=ItemOut)
def get_item(item_id: int, db: Session = Depends(get_db)):
    item = db.scalar(select(Item).where(Item.id == item_id).options(joinedload(Item.category), joinedload(Item.supplier), joinedload(Item.location)))
    if not item:
        raise HTTPException(404, "Prece nav atrasta")
    return item_out(item)


@router.post("", response_model=ItemOut, status_code=201)
def create_item(data: ItemIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    validate_relations(db, data)
    item = Item(**data.model_dump())
    db.add(item)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "SKU jau tiek izmantots")
    log_activity(db, user, "create", "item", item.id, f"Izveidota prece ŌĆ£{item.name}ŌĆØ")
    db.commit()
    return get_item(item.id, db)


@router.put("/{item_id}", response_model=ItemOut)
def update_item(item_id: int, data: ItemUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(404, "Prece nav atrasta")
    validate_relations(db, data)
    for key, value in data.model_dump().items():
        setattr(item, key, value)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "SKU jau tiek izmantots")
    log_activity(db, user, "update", "item", item.id, f"Atjaunin?üta prece ŌĆ£{item.name}ŌĆØ")
    db.commit()
    return get_item(item.id, db)


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(404, "Prece nav atrasta")
    name = item.name
    if item.transfers:
        raise HTTPException(409, "Preci ar p?ürvieto?Īanas v?ōsturi nevar dz?ōst")
    db.delete(item)
    log_activity(db, user, "delete", "item", item_id, f"Dz?ōsta prece ŌĆ£{name}ŌĆØ")
    db.commit()


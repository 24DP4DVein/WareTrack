from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.auth.dependencies import get_current_user, require_operational
from app.database import get_db
from app.models import Category, InventoryBalance, Item, Location, StockMovement, Supplier, User
from app.schemas import ItemIn, ItemList, ItemOut, ItemUpdate
from app.services.activity import log_activity

router = APIRouter(prefix="/items", tags=["Preces"])


def item_out(item: Item) -> ItemOut:
    balances = sorted(item.inventory_balances, key=lambda balance: (-balance.quantity, balance.location_id))
    total_stock = sum(balance.quantity for balance in balances)
    primary = balances[0] if balances else None
    status = (
        "critical"
        if total_stock <= item.min_stock * 0.3
        else "low"
        if total_stock < item.min_stock
        else "ok"
    )
    return ItemOut.model_validate({
        "id": item.id,
        "name": item.name,
        "sku": item.sku,
        "category_id": item.category_id,
        "supplier_id": item.supplier_id,
        "location_id": primary.location_id if primary else 0,
        "stock": total_stock,
        "min_stock": item.min_stock,
        "price": item.price,
        "description": item.description,
        "category_name": item.category.name,
        "supplier_name": item.supplier.name if item.supplier else None,
        "location_name": primary.location.name if primary else None,
        "locations": [
            {"location_id": balance.location_id, "location_name": balance.location.name, "quantity": balance.quantity}
            for balance in balances
        ],
        "status": status,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    })


def validate_relations(db: Session, data: ItemIn):
    if not db.get(Category, data.category_id):
        raise HTTPException(422, "Norādītā kategorija neeksistē")
    if not db.get(Location, data.location_id):
        raise HTTPException(422, "Norādītā noliktavas vieta neeksistē")
    if data.supplier_id and not db.get(Supplier, data.supplier_id):
        raise HTTPException(422, "Norādītais piegādātājs neeksistē")


@router.get("", response_model=ItemList)
def list_items(
    search: str = "",
    category: int | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stock_expr = (
        select(func.coalesce(func.sum(InventoryBalance.quantity), 0))
        .where(InventoryBalance.item_id == Item.id)
        .scalar_subquery()
    )
    query = select(Item)

    if search.strip():
        q = f"%{search.strip()}%"
        query = query.where(
            or_(Item.name.ilike(q), Item.sku.ilike(q))
        )

    if category is not None:
        query = query.where(Item.category_id == category)

    if status in {"ok", "low", "critical"}:
        if status == "critical":
            query = query.where(stock_expr <= Item.min_stock * 0.3)
        elif status == "low":
            query = query.where(
                stock_expr < Item.min_stock,
                stock_expr > Item.min_stock * 0.3,
            )
        else:
            query = query.where(stock_expr >= Item.min_stock)

    total = db.scalar(
        select(func.count()).select_from(query.subquery())
    ) or 0

    items_query = (
        query.options(
            joinedload(Item.category),
            joinedload(Item.supplier),
            selectinload(Item.inventory_balances).joinedload(InventoryBalance.location),
        )
        .order_by(Item.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    items = db.scalars(items_query).unique().all()

    return ItemList(
        items=[item_out(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{item_id}", response_model=ItemOut)
def get_item(item_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    item = db.scalar(
        select(Item)
        .where(Item.id == item_id)
        .options(
            joinedload(Item.category),
            joinedload(Item.supplier),
            selectinload(Item.inventory_balances).joinedload(InventoryBalance.location),
        )
    )
    if not item:
        raise HTTPException(404, "Prece nav atrasta")
    return item_out(item)


@router.post("", response_model=ItemOut, status_code=201)
def create_item(
    data: ItemIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_operational),
):
    validate_relations(db, data)
    if db.scalar(select(Item.id).where(Item.sku == data.sku)):
        raise HTTPException(409, "SKU jau tiek izmantots")
    values = data.model_dump()
    location_id = values.pop("location_id")
    stock = values.pop("stock")
    location = db.get(Location, location_id)
    used = db.scalar(
        select(func.coalesce(func.sum(InventoryBalance.quantity), 0)).where(
            InventoryBalance.location_id == location_id
        )
    ) or 0
    if used + stock > location.capacity:
        raise HTTPException(422, "Noliktavas vietā nepietiek ietilpības")
    item = Item(**values)
    db.add(item)

    try:
        db.flush()
        db.add(InventoryBalance(item_id=item.id, location_id=location_id, quantity=stock))
        if stock:
            db.add(StockMovement(
                item_id=item.id,
                destination_location_id=location_id,
                quantity=stock,
                action="initial_receipt",
                user_id=user.id,
            ))
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "SKU jau tiek izmantots")
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(500, "Neizdevās saglabāt preci")

    try:
        log_activity(
            db, user, "create", "item", item.id,
            f"Izveidota prece: {item.name}",
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(500, "Neizdevās saglabāt preci")

    return get_item(item.id, db)


@router.put("/{item_id}", response_model=ItemOut)
def update_item(
    item_id: int,
    data: ItemUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_operational),
):
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(404, "Prece nav atrasta")

    validate_relations(db, data)
    balances = list(db.scalars(
        select(InventoryBalance)
        .where(InventoryBalance.item_id == item.id)
        .order_by(InventoryBalance.quantity.desc())
    ))
    values = data.model_dump()
    location_id = values.pop("location_id")
    requested_stock = values.pop("stock")
    current_stock = sum(balance.quantity for balance in balances)
    if len(balances) > 1 and (requested_stock != current_stock or location_id != balances[0].location_id):
        raise HTTPException(409, "Sadalīts krājums jāmaina ar pārvietojumu")
    if db.scalar(
        select(Item.id).where(Item.sku == data.sku, Item.id != item.id)
    ):
        raise HTTPException(409, "SKU jau tiek izmantots")
    if len(balances) == 1:
        target_used = db.scalar(
            select(func.coalesce(func.sum(InventoryBalance.quantity), 0)).where(
                InventoryBalance.location_id == location_id
            )
        ) or 0
        current_at_target = balances[0].quantity if balances[0].location_id == location_id else 0
        target_location = db.get(Location, location_id)
        if target_used - current_at_target + requested_stock > target_location.capacity:
            raise HTTPException(422, "Noliktavas vietā nepietiek ietilpības")
        balances[0].location_id = location_id
        balances[0].quantity = requested_stock
    elif not balances:
        db.add(InventoryBalance(item_id=item.id, location_id=location_id, quantity=requested_stock))

    for key, value in values.items():
        setattr(item, key, value)

    if len(balances) == 1 and requested_stock != current_stock:
        db.add(StockMovement(
            item_id=item.id,
            source_location_id=location_id if requested_stock < current_stock else None,
            destination_location_id=location_id if requested_stock > current_stock else None,
            quantity=abs(requested_stock - current_stock),
            action="inventory_adjustment",
            user_id=user.id,
        ))

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "SKU jau tiek izmantots")
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(500, "Neizdevās atjaunināt preci")

    try:
        log_activity(
            db, user, "update", "item", item.id,
            f"Atjaunināta prece: {item.name}",
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(500, "Neizdevās atjaunināt preci")

    return get_item(item.id, db)


@router.delete("/{item_id}", status_code=204)
def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_operational),
):
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(404, "Prece nav atrasta")

    name = item.name

    if item.transfers:
        raise HTTPException(
            409,
            "Preci ar pārvietošanas vēsturi nevar dzēst",
        )

    try:
        db.delete(item)
        log_activity(
            db, user, "delete", "item", item.id,
            f"Dzēsta prece: {name}",
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(500, "Neizdevās dzēst preci")

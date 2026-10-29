from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.auth.company_access import (
    CompanyAccessContext,
    require_company_edit_access,
    require_company_manager_access,
    require_company_read_access,
)
from app.database import get_db
from app.models import Category, InventoryBalance, Item, Location, Supplier
from app.schemas import (
    CategoryIn, CategoryOut, ItemIn, ItemList, ItemOut, ItemUpdate,
    LocationIn, LocationOut, SupplierIn, SupplierOut,
)
from app.services.activity import log_activity

router = APIRouter(prefix="/companies/{company_id}", tags=["Company inventory"])
legacy = APIRouter(tags=["Disabled legacy warehouse API"])


def _item_out(item: Item) -> ItemOut:
    status = "critical" if item.stock <= item.min_stock * .3 else "low" if item.stock < item.min_stock else "ok"
    return ItemOut.model_validate({
        "id": item.id, "name": item.name, "sku": item.sku,
        "category_id": item.category_id, "supplier_id": item.supplier_id,
        "location_id": item.location_id, "stock": item.stock,
        "min_stock": item.min_stock, "price": item.price,
        "description": item.description, "category_name": item.category.name,
        "supplier_name": item.supplier.name if item.supplier else None,
        "location_name": item.location.name, "status": status,
        "created_at": item.created_at, "updated_at": item.updated_at,
    })


def _load_item(db: Session, company_id: int, item_id: int) -> Item:
    item = db.scalar(
        select(Item).where(Item.company_id == company_id, Item.id == item_id).options(
            joinedload(Item.category), joinedload(Item.supplier), joinedload(Item.location)
        )
    )
    if item is None:
        raise HTTPException(404, "Item not found")
    return item


def _validate_item_relations(db: Session, company_id: int, data: ItemIn) -> None:
    checks = (
        (Category, data.category_id, "Category"),
        (Location, data.location_id, "Location"),
        (Supplier, data.supplier_id, "Supplier"),
    )
    for model, resource_id, label in checks:
        if resource_id is not None and db.scalar(select(model.id).where(
            model.id == resource_id, model.company_id == company_id
        )) is None:
            raise HTTPException(422, f"{label} does not belong to this company")


def _conflict(db: Session, model, company_id: int, field, value, *, exclude_id=None) -> bool:
    query = select(model.id).where(model.company_id == company_id, field == value)
    if exclude_id is not None:
        query = query.where(model.id != exclude_id)
    return db.scalar(query) is not None


def _flush_or_conflict(db: Session, detail: str) -> None:
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, detail) from exc


@router.get("/items", response_model=ItemList)
def item_list(
    company_id: int, search: str = "", category: int | None = None,
    status: str | None = None, page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100), db: Session = Depends(get_db),
    _: CompanyAccessContext = Depends(require_company_read_access),
):
    query = select(Item).where(Item.company_id == company_id).options(
        joinedload(Item.category), joinedload(Item.supplier), joinedload(Item.location)
    )
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(or_(Item.name.ilike(pattern), Item.sku.ilike(pattern)))
    if category is not None:
        query = query.where(Item.category_id == category)
    company_items = list(db.scalars(query.order_by(Item.created_at.desc())).unique())
    if status in {"ok", "low", "critical"}:
        company_items = [item for item in company_items if _item_out(item).status == status]
    total = len(company_items)
    selected = company_items[(page - 1) * page_size:page * page_size]
    return ItemList(items=[_item_out(item) for item in selected], total=total,
                    page=page, page_size=page_size)


@router.get("/items/{item_id}", response_model=ItemOut)
def item_get(company_id: int, item_id: int, db: Session = Depends(get_db),
             _: CompanyAccessContext = Depends(require_company_read_access)):
    return _item_out(_load_item(db, company_id, item_id))


@router.post("/items", response_model=ItemOut, status_code=201)
def item_create(company_id: int, data: ItemIn, db: Session = Depends(get_db),
                access: CompanyAccessContext = Depends(require_company_edit_access)):
    _validate_item_relations(db, company_id, data)
    if _conflict(db, Item, company_id, Item.sku, data.sku):
        raise HTTPException(409, "SKU already exists in this company")
    item = Item(company_id=company_id, **data.model_dump())
    db.add(item)
    _flush_or_conflict(db, "SKU already exists in this company")
    db.add(InventoryBalance(
        company_id=company_id, item_id=item.id, location_id=item.location_id,
        quantity=item.stock, reserved=0,
    ))
    log_activity(db, access.user, "create", "item", item.id,
                 f'Created item "{item.name}"', company_id=company_id)
    db.commit()
    return _item_out(_load_item(db, company_id, item.id))


@router.put("/items/{item_id}", response_model=ItemOut)
def item_update(company_id: int, item_id: int, data: ItemUpdate,
                db: Session = Depends(get_db),
                access: CompanyAccessContext = Depends(require_company_edit_access)):
    item = _load_item(db, company_id, item_id)
    _validate_item_relations(db, company_id, data)
    balances = list(db.scalars(select(InventoryBalance).where(
        InventoryBalance.company_id == company_id,
        InventoryBalance.item_id == item.id,
    )))
    if balances and (
        data.stock != sum(balance.quantity for balance in balances)
        or data.location_id != item.location_id
    ):
        raise HTTPException(
            409, "Ledger-managed stock and location cannot be changed through item update"
        )
    if _conflict(db, Item, company_id, Item.sku, data.sku, exclude_id=item.id):
        raise HTTPException(409, "SKU already exists in this company")
    for key, value in data.model_dump().items():
        setattr(item, key, value)
    _flush_or_conflict(db, "SKU already exists in this company")
    log_activity(db, access.user, "update", "item", item.id,
                 f'Updated item "{item.name}"', company_id=company_id)
    db.commit()
    return _item_out(_load_item(db, company_id, item.id))


@router.delete("/items/{item_id}", status_code=204)
def item_delete(company_id: int, item_id: int, db: Session = Depends(get_db),
                access: CompanyAccessContext = Depends(require_company_edit_access)):
    item = _load_item(db, company_id, item_id)
    if item.transfers:
        raise HTTPException(409, "Item with transfer history cannot be deleted")
    name = item.name
    for balance in list(item.inventory_balances):
        db.delete(balance)
    db.delete(item)
    log_activity(db, access.user, "delete", "item", item_id,
                 f'Deleted item "{name}"', company_id=company_id)
    db.commit()
    return Response(status_code=204)


def _category_out(category: Category, count: int) -> CategoryOut:
    return CategoryOut(id=category.id, name=category.name, description=category.description,
                       icon=category.icon, color=category.color, item_count=count,
                       created_at=category.created_at)


@router.get("/categories", response_model=list[CategoryOut])
def category_list(company_id: int, db: Session = Depends(get_db),
                  _: CompanyAccessContext = Depends(require_company_read_access)):
    rows = db.execute(
        select(Category, func.count(Item.id)).where(Category.company_id == company_id)
        .outerjoin(Item, and_(Item.category_id == Category.id, Item.company_id == company_id))
        .group_by(Category.id).order_by(Category.name)
    ).all()
    return [_category_out(category, count) for category, count in rows]


@router.get("/categories/{category_id}", response_model=CategoryOut)
def category_get(company_id: int, category_id: int, db: Session = Depends(get_db),
                 _: CompanyAccessContext = Depends(require_company_read_access)):
    category = db.scalar(select(Category).where(
        Category.company_id == company_id, Category.id == category_id
    ))
    if category is None:
        raise HTTPException(404, "Category not found")
    count = db.scalar(select(func.count(Item.id)).where(
        Item.company_id == company_id, Item.category_id == category.id
    )) or 0
    return _category_out(category, count)


@router.post("/categories", response_model=CategoryOut, status_code=201)
def category_create(company_id: int, data: CategoryIn, db: Session = Depends(get_db),
                    access: CompanyAccessContext = Depends(require_company_manager_access)):
    if _conflict(db, Category, company_id, Category.name, data.name):
        raise HTTPException(409, "Category name already exists in this company")
    category = Category(company_id=company_id, **data.model_dump())
    db.add(category)
    _flush_or_conflict(db, "Category name already exists in this company")
    log_activity(db, access.user, "create", "category", category.id,
                 f'Created category "{category.name}"', company_id=company_id)
    db.commit(); db.refresh(category)
    return _category_out(category, 0)


@router.put("/categories/{category_id}", response_model=CategoryOut)
def category_update(company_id: int, category_id: int, data: CategoryIn,
                    db: Session = Depends(get_db),
                    access: CompanyAccessContext = Depends(require_company_manager_access)):
    category = db.scalar(select(Category).where(
        Category.company_id == company_id, Category.id == category_id
    ))
    if category is None:
        raise HTTPException(404, "Category not found")
    if _conflict(db, Category, company_id, Category.name, data.name, exclude_id=category.id):
        raise HTTPException(409, "Category name already exists in this company")
    for key, value in data.model_dump().items(): setattr(category, key, value)
    _flush_or_conflict(db, "Category name already exists in this company")
    log_activity(db, access.user, "update", "category", category.id,
                 f'Updated category "{category.name}"', company_id=company_id)
    count = db.scalar(select(func.count(Item.id)).where(
        Item.company_id == company_id, Item.category_id == category.id
    )) or 0
    db.commit(); db.refresh(category)
    return _category_out(category, count)


@router.delete("/categories/{category_id}", status_code=204)
def category_delete(company_id: int, category_id: int, db: Session = Depends(get_db),
                    access: CompanyAccessContext = Depends(require_company_manager_access)):
    category = db.scalar(select(Category).where(
        Category.company_id == company_id, Category.id == category_id
    ))
    if category is None: raise HTTPException(404, "Category not found")
    if db.scalar(select(Item.id).where(Item.company_id == company_id, Item.category_id == category.id)):
        raise HTTPException(409, "Category is used by items")
    name = category.name; db.delete(category)
    log_activity(db, access.user, "delete", "category", category_id,
                 f'Deleted category "{name}"', company_id=company_id)
    db.commit()
    return Response(status_code=204)


@router.get("/suppliers", response_model=list[SupplierOut])
def supplier_list(company_id: int, db: Session = Depends(get_db),
                  _: CompanyAccessContext = Depends(require_company_read_access)):
    return list(db.scalars(select(Supplier).where(
        Supplier.company_id == company_id
    ).order_by(Supplier.name)))


@router.get("/suppliers/{supplier_id}", response_model=SupplierOut)
def supplier_get(company_id: int, supplier_id: int, db: Session = Depends(get_db),
                 _: CompanyAccessContext = Depends(require_company_read_access)):
    supplier = db.scalar(select(Supplier).where(
        Supplier.company_id == company_id, Supplier.id == supplier_id
    ))
    if supplier is None: raise HTTPException(404, "Supplier not found")
    return supplier


@router.post("/suppliers", response_model=SupplierOut, status_code=201)
def supplier_create(company_id: int, data: SupplierIn, db: Session = Depends(get_db),
                    access: CompanyAccessContext = Depends(require_company_manager_access)):
    if (_conflict(db, Supplier, company_id, Supplier.name, data.name)
            or _conflict(db, Supplier, company_id, Supplier.email, str(data.email))):
        raise HTTPException(409, "Supplier name or email already exists in this company")
    supplier = Supplier(company_id=company_id, **data.model_dump())
    db.add(supplier)
    _flush_or_conflict(db, "Supplier name or email already exists in this company")
    log_activity(db, access.user, "create", "supplier", supplier.id,
                 f'Created supplier "{supplier.name}"', company_id=company_id)
    db.commit(); db.refresh(supplier)
    return supplier


@router.put("/suppliers/{supplier_id}", response_model=SupplierOut)
def supplier_update(company_id: int, supplier_id: int, data: SupplierIn,
                    db: Session = Depends(get_db),
                    access: CompanyAccessContext = Depends(require_company_manager_access)):
    supplier = db.scalar(select(Supplier).where(
        Supplier.company_id == company_id, Supplier.id == supplier_id
    ))
    if supplier is None: raise HTTPException(404, "Supplier not found")
    if (_conflict(db, Supplier, company_id, Supplier.name, data.name, exclude_id=supplier.id)
            or _conflict(db, Supplier, company_id, Supplier.email, str(data.email), exclude_id=supplier.id)):
        raise HTTPException(409, "Supplier name or email already exists in this company")
    for key, value in data.model_dump().items(): setattr(supplier, key, value)
    _flush_or_conflict(db, "Supplier name or email already exists in this company")
    log_activity(db, access.user, "update", "supplier", supplier.id,
                 f'Updated supplier "{supplier.name}"', company_id=company_id)
    db.commit(); db.refresh(supplier)
    return supplier


@router.delete("/suppliers/{supplier_id}", status_code=204)
def supplier_delete(company_id: int, supplier_id: int, db: Session = Depends(get_db),
                    access: CompanyAccessContext = Depends(require_company_manager_access)):
    supplier = db.scalar(select(Supplier).where(
        Supplier.company_id == company_id, Supplier.id == supplier_id
    ))
    if supplier is None: raise HTTPException(404, "Supplier not found")
    if db.scalar(select(Item.id).where(Item.company_id == company_id, Item.supplier_id == supplier.id)):
        raise HTTPException(409, "Supplier is used by items")
    name = supplier.name; db.delete(supplier)
    log_activity(db, access.user, "delete", "supplier", supplier_id,
                 f'Deleted supplier "{name}"', company_id=company_id)
    db.commit()
    return Response(status_code=204)


def _location_out(location: Location, used: int) -> LocationOut:
    return LocationOut(id=location.id, code=location.code, name=location.name,
                       capacity=location.capacity, used_capacity=used,
                       created_at=location.created_at)


@router.get("/locations", response_model=list[LocationOut])
def location_list(company_id: int, db: Session = Depends(get_db),
                  _: CompanyAccessContext = Depends(require_company_read_access)):
    rows = db.execute(
        select(Location, func.coalesce(func.sum(Item.stock), 0))
        .where(Location.company_id == company_id)
        .outerjoin(Item, and_(Item.location_id == Location.id, Item.company_id == company_id))
        .group_by(Location.id).order_by(Location.code)
    ).all()
    return [_location_out(location, int(used)) for location, used in rows]


@router.get("/locations/{location_id}", response_model=LocationOut)
def location_get(company_id: int, location_id: int, db: Session = Depends(get_db),
                 _: CompanyAccessContext = Depends(require_company_read_access)):
    location = db.scalar(select(Location).where(
        Location.company_id == company_id, Location.id == location_id
    ))
    if location is None: raise HTTPException(404, "Location not found")
    used = db.scalar(select(func.coalesce(func.sum(Item.stock), 0)).where(
        Item.company_id == company_id, Item.location_id == location.id
    )) or 0
    return _location_out(location, int(used))


@router.post("/locations", response_model=LocationOut, status_code=201)
def location_create(company_id: int, data: LocationIn, db: Session = Depends(get_db),
                    access: CompanyAccessContext = Depends(require_company_manager_access)):
    if _conflict(db, Location, company_id, Location.code, data.code):
        raise HTTPException(409, "Location code already exists in this company")
    location = Location(company_id=company_id, **data.model_dump())
    db.add(location)
    _flush_or_conflict(db, "Location code already exists in this company")
    log_activity(db, access.user, "create", "location", location.id,
                 f'Created location "{location.name}"', company_id=company_id)
    db.commit(); db.refresh(location)
    return _location_out(location, 0)


@router.put("/locations/{location_id}", response_model=LocationOut)
def location_update(company_id: int, location_id: int, data: LocationIn,
                    db: Session = Depends(get_db),
                    access: CompanyAccessContext = Depends(require_company_manager_access)):
    location = db.scalar(select(Location).where(
        Location.company_id == company_id, Location.id == location_id
    ))
    if location is None: raise HTTPException(404, "Location not found")
    if _conflict(db, Location, company_id, Location.code, data.code, exclude_id=location.id):
        raise HTTPException(409, "Location code already exists in this company")
    for key, value in data.model_dump().items(): setattr(location, key, value)
    _flush_or_conflict(db, "Location code already exists in this company")
    log_activity(db, access.user, "update", "location", location.id,
                 f'Updated location "{location.name}"', company_id=company_id)
    used = db.scalar(select(func.coalesce(func.sum(Item.stock), 0)).where(
        Item.company_id == company_id, Item.location_id == location.id
    )) or 0
    db.commit(); db.refresh(location)
    return _location_out(location, int(used))


@router.delete("/locations/{location_id}", status_code=204)
def location_delete(company_id: int, location_id: int, db: Session = Depends(get_db),
                    access: CompanyAccessContext = Depends(require_company_manager_access)):
    location = db.scalar(select(Location).where(
        Location.company_id == company_id, Location.id == location_id
    ))
    if location is None: raise HTTPException(404, "Location not found")
    if db.scalar(select(Item.id).where(Item.company_id == company_id, Item.location_id == location.id)):
        raise HTTPException(409, "Location is used by items")
    if db.scalar(select(InventoryBalance.id).where(
        InventoryBalance.company_id == company_id,
        InventoryBalance.location_id == location.id,
    )):
        raise HTTPException(409, "Location has inventory balances")
    name = location.name; db.delete(location)
    log_activity(db, access.user, "delete", "location", location_id,
                 f'Deleted location "{name}"', company_id=company_id)
    db.commit()
    return Response(status_code=204)


def _legacy_disabled():
    raise HTTPException(410, "Use a company-scoped warehouse endpoint")


for path in ("/items", "/categories", "/suppliers", "/locations", "/transfers"):
    legacy.add_api_route(path, _legacy_disabled, methods=["GET", "POST"])
    legacy.add_api_route(path + "/{resource_id}", _legacy_disabled,
                         methods=["GET", "PUT", "PATCH", "DELETE"])
for path in ("/dashboard", "/reports", "/activity"):
    legacy.add_api_route(path, _legacy_disabled, methods=["GET"])


from app.routers.company_operations import router as company_operations_router

router.include_router(company_operations_router)

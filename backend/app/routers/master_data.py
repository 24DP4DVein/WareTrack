from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_operational
from app.database import get_db
from app.models import Category, InventoryBalance, Item, Location, Supplier, User
from app.schemas import CategoryIn, CategoryOut, LocationIn, LocationOut, SupplierIn, SupplierOut
from app.services.activity import log_activity

categories = APIRouter(prefix="/categories", tags=["Kategorijas"])
suppliers = APIRouter(prefix="/suppliers", tags=["Piegādātāji"])
locations = APIRouter(prefix="/locations", tags=["Noliktavas vietas"])


def category_out(c: Category, count: int) -> CategoryOut:
    return CategoryOut(id=c.id, name=c.name, description=c.description, icon=c.icon, color=c.color,
                       item_count=count, created_at=c.created_at)


@categories.get("", response_model=list[CategoryOut])
def category_list(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.execute(select(Category, func.count(Item.id)).outerjoin(Item).group_by(Category.id).order_by(Category.name)).all()
    return [category_out(c, count) for c, count in rows]


@categories.get("/{category_id}", response_model=CategoryOut)
def category_get(category_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    category = db.get(Category, category_id)
    if not category:
        raise HTTPException(404, "Kategorija nav atrasta")
    count = db.scalar(select(func.count(Item.id)).where(Item.category_id == category.id)) or 0
    return category_out(category, count)


@categories.post("", response_model=CategoryOut, status_code=201)
def category_create(data: CategoryIn, db: Session = Depends(get_db), user: User = Depends(require_operational)):
    category = Category(**data.model_dump())
    db.add(category)
    try:
        db.flush()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, "Kategorija ar šādu nosaukumu jau pastāv")
    log_activity(db, user, "create", "category", category.id, f"Izveidota kategorija “{category.name}”")
    db.commit(); db.refresh(category)
    return category_out(category, 0)


@categories.put("/{category_id}", response_model=CategoryOut)
def category_update(category_id: int, data: CategoryIn, db: Session = Depends(get_db), user: User = Depends(require_operational)):
    category = db.get(Category, category_id)
    if not category: raise HTTPException(404, "Kategorija nav atrasta")
    for key, value in data.model_dump().items(): setattr(category, key, value)
    try: db.flush()
    except IntegrityError: db.rollback(); raise HTTPException(409, "Kategorija ar šādu nosaukumu jau pastāv")
    log_activity(db, user, "update", "category", category.id, f"Atjaunināta kategorija “{category.name}”")
    count = db.scalar(select(func.count(Item.id)).where(Item.category_id == category.id)) or 0
    db.commit(); db.refresh(category)
    return category_out(category, count)


@categories.delete("/{category_id}", status_code=204)
def category_delete(category_id: int, db: Session = Depends(get_db), user: User = Depends(require_operational)):
    category = db.get(Category, category_id)
    if not category: raise HTTPException(404, "Kategorija nav atrasta")
    if category.items: raise HTTPException(409, "Nevar dzēst kategoriju, kurai piesaistītas preces")
    name = category.name; db.delete(category)
    log_activity(db, user, "delete", "category", category_id, f"Dzēsta kategorija “{name}”")
    db.commit()


@suppliers.get("", response_model=list[SupplierOut])
def supplier_list(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return list(db.scalars(select(Supplier).order_by(Supplier.name)))


@suppliers.get("/{supplier_id}", response_model=SupplierOut)
def supplier_get(supplier_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(404, "Piegādātājs nav atrasts")
    return supplier


@suppliers.post("", response_model=SupplierOut, status_code=201)
def supplier_create(data: SupplierIn, db: Session = Depends(get_db), user: User = Depends(require_operational)):
    supplier = Supplier(**data.model_dump()); db.add(supplier)
    try: db.flush()
    except IntegrityError: db.rollback(); raise HTTPException(409, "Piegādātāja nosaukums vai e-pasts jau tiek izmantots")
    log_activity(db, user, "create", "supplier", supplier.id, f"Izveidots piegādātājs “{supplier.name}”")
    db.commit(); db.refresh(supplier); return supplier


@suppliers.put("/{supplier_id}", response_model=SupplierOut)
def supplier_update(supplier_id: int, data: SupplierIn, db: Session = Depends(get_db), user: User = Depends(require_operational)):
    supplier = db.get(Supplier, supplier_id)
    if not supplier: raise HTTPException(404, "Piegādātājs nav atrasts")
    for key, value in data.model_dump().items(): setattr(supplier, key, value)
    try: db.flush()
    except IntegrityError: db.rollback(); raise HTTPException(409, "Piegādātāja nosaukums vai e-pasts jau tiek izmantots")
    log_activity(db, user, "update", "supplier", supplier.id, f"Atjaunināts piegādātājs “{supplier.name}”")
    db.commit(); db.refresh(supplier); return supplier


@suppliers.delete("/{supplier_id}", status_code=204)
def supplier_delete(supplier_id: int, db: Session = Depends(get_db), user: User = Depends(require_operational)):
    supplier = db.get(Supplier, supplier_id)
    if not supplier: raise HTTPException(404, "Piegādātājs nav atrasts")
    if supplier.items: raise HTTPException(409, "Nevar dzēst piegādātāju, kuram piesaistītas preces")
    name = supplier.name; db.delete(supplier)
    log_activity(db, user, "delete", "supplier", supplier_id, f"Dzēsts piegādātājs “{name}”")
    db.commit()


def location_out(location: Location, used: int) -> LocationOut:
    return LocationOut(id=location.id, code=location.code, name=location.name, capacity=location.capacity,
                       used_capacity=used, created_at=location.created_at)


@locations.get("", response_model=list[LocationOut])
def location_list(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.execute(
        select(Location, func.coalesce(func.sum(InventoryBalance.quantity), 0))
        .outerjoin(InventoryBalance)
        .group_by(Location.id)
        .order_by(Location.code)
    ).all()
    return [location_out(location, int(used)) for location, used in rows]


@locations.get("/{location_id}", response_model=LocationOut)
def location_get(location_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    location = db.get(Location, location_id)
    if not location:
        raise HTTPException(404, "Noliktavas vieta nav atrasta")
    used = db.scalar(
        select(func.coalesce(func.sum(InventoryBalance.quantity), 0))
        .where(InventoryBalance.location_id == location.id)
    ) or 0
    return location_out(location, int(used))


@locations.post("", response_model=LocationOut, status_code=201)
def location_create(data: LocationIn, db: Session = Depends(get_db), user: User = Depends(require_operational)):
    location = Location(**data.model_dump()); db.add(location)
    try: db.flush()
    except IntegrityError: db.rollback(); raise HTTPException(409, "Vietas kods jau tiek izmantots")
    log_activity(db, user, "create", "location", location.id, f"Izveidota vieta “{location.name}”")
    db.commit(); db.refresh(location); return location_out(location, 0)


@locations.put("/{location_id}", response_model=LocationOut)
def location_update(location_id: int, data: LocationIn, db: Session = Depends(get_db), user: User = Depends(require_operational)):
    location = db.get(Location, location_id)
    if not location: raise HTTPException(404, "Noliktavas vieta nav atrasta")
    used = db.scalar(
        select(func.coalesce(func.sum(InventoryBalance.quantity), 0))
        .where(InventoryBalance.location_id == location.id)
    ) or 0
    if data.capacity < used:
        raise HTTPException(409, "Ietilpība nevar būt mazāka par pašreizējo krājumu")
    for key, value in data.model_dump().items(): setattr(location, key, value)
    db.commit(); db.refresh(location)
    return location_out(location, int(used))


@locations.delete("/{location_id}", status_code=204)
def location_delete(location_id: int, db: Session = Depends(get_db), user: User = Depends(require_operational)):
    location = db.get(Location, location_id)
    if not location: raise HTTPException(404, "Noliktavas vieta nav atrasta")
    if location.inventory_balances: raise HTTPException(409, "Nevar dzēst vietu, kurā ir krājums")
    db.delete(location); db.commit()

